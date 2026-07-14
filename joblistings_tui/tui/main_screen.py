import pandas as pd
from collections import namedtuple
from rich.text import Text
from typing import Callable, Sequence, Union

import pyperclip

from joblistings_tui.backend.storage import load_existing_jobs, update_job_fields
from joblistings_tui.backend.filter_jobs import filter_jobs_df

from textual.coordinate import Coordinate
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer


from .widgets import VimDataTable

from .job_description import JobDetailScreen, get_job_url
from .scrape_menu import ScrapeScreen
from .filter_bar import FilterBar

TUIColumn = namedtuple("TUIColumn", ["name", "width"])
columns = [
    TUIColumn("id", 0),
    TUIColumn("title", 60),
    TUIColumn("company", 30),
    TUIColumn("location", 20),
    TUIColumn("date_posted", 15),
    TUIColumn("fit_score", 10),
    TUIColumn("applied", 10),
]


class JobListingsTUI(App):
    """A Textual app to display job listings."""

    CSS_PATH = "tui.tcss"
    BINDINGS = [
        Binding("/", "filter", "Filter"),
        Binding("q", "quit", "Quit"),
        Binding("s", "toggle_save_job", "Save"),
        Binding("x", "hide_job", "Hide"),
        Binding("y", "yank_job_url", "Copy URL"),
        Binding("o", "open_job", "Open"),
        Binding("enter", "open_job", "Open", show=False),
        Binding("D", "toggle_dark", "Theme"),
        Binding("S", "open_scrape_menu", "Scrape"),
    ]

    def action_open_job(self) -> None:
        table = self.query_one("#jobs", VimDataTable)
        if table.cursor_row is not None:
            job_id = table.get_cell_at(Coordinate(table.cursor_row, 0)).plain
            jobdetails = self._jobs[self._jobs["id"] == job_id].iloc[0].to_dict()
            self.push_screen(
                JobDetailScreen(jobdetails, custom_hook=self._custom_hook),
                callback=self._refresh_job_row,
            )

    def _get_job_id_at_cursor(self) -> str | None:
        table = self.query_one("#jobs", VimDataTable)
        if table.cursor_row is None:
            return
        return table.get_cell_at(Coordinate(table.cursor_row, 0)).plain

    def _update_job_field(
        self,
        job_id: str,
        fields: Union[str, Sequence[str]],
        values: Union[float, bool, str, Sequence[Union[float, bool, str]]],
    ) -> None:
        update_job_fields(job_id, fields, values)

    def _refresh_after_filter(self, result) -> None:
        if not (isinstance(result, str)):
            return
        filtered_jobs = filter_jobs_df(result, self._jobs)
        self._render_table(filtered_jobs, sort=False)

    def action_filter(self) -> None:
        self.push_screen(FilterBar(), callback=self._refresh_after_filter)

    def action_yank_job_url(self) -> None:
        job_id = self._get_job_id_at_cursor()
        job = self._jobs_by_id[job_id]
        url = get_job_url(job)
        pyperclip.copy(url)
        self.notify(
            f"URL copied for job: {job['title']} at {job['company']}",
            timeout=3,
            severity="information",
        )

    def action_hide_job(self) -> None:
        job_id = self._get_job_id_at_cursor()
        if job_id is None:
            return
        self._update_job_field(job_id, "hidden", True)
        self._jobs.loc[self._jobs["id"] == job_id, "hidden"] = True
        self._refresh_job_row({"job_id": job_id, "updated": {"hidden": True}})
        job = self._jobs_by_id[job_id]
        self.notify(
            f"Hid job {job['title']} at {job['company']}",
            timeout=3,
            severity="information",
        )

    def action_toggle_save_job(self) -> None:
        job_id = self._get_job_id_at_cursor()
        if job_id is None:
            return
        job = self._jobs_by_id[job_id]
        newval = not (job["saved"])
        self._update_job_field(job_id, "saved", newval)
        self._jobs.loc[self._jobs["id"] == job_id, "saved"] = newval
        self._refresh_job_row({"job_id": job_id, "updated": {"saved": newval}})

    def _refresh_job_row(self, result):
        if result and result.get("updated"):
            updated_fields = result["updated"]
            job_id = result["job_id"]
            # Modify the in-memory DataFrame
            job_index = self._jobs.index[self._jobs["id"] == result["job_id"]][0]
            for field, value in updated_fields.items():
                self._jobs.at[job_index, field] = value
            self._jobs_by_id[job_id] = self._jobs.loc[job_index]
            # Re-render table row
            table = self.query_one("#jobs", VimDataTable)
            hidden = updated_fields.get("hidden", False)
            if hidden:
                table.remove_row(job_id)
            else:
                job = self._jobs_by_id[job_id]
                row_style = self._get_row_format(job)
                for column in columns:
                    table.update_cell(
                        row_key=job_id,
                        column_key=column.name,
                        value=Text(str(job[column.name]), style=row_style),
                    )

    def action_open_scrape_menu(self) -> None:
        self.push_screen(ScrapeScreen(), callback=self._refresh_after_scrape)

    def _refresh_after_scrape(self, result) -> None:
        if not result:
            return
        new_jobs = result["new_jobs"]
        if new_jobs.empty:
            return
        self._session_new_job_ids.update(new_jobs["id"].unique())
        self._jobs = pd.concat([self._jobs, new_jobs], ignore_index=True)
        self._render_table(self._jobs)

    def compose(self) -> ComposeResult:
        yield Footer()
        yield VimDataTable(id="jobs")

    def __init__(self, custom_hook: Callable[[dict], str | None] | None = None) -> None:
        super().__init__()
        self._jobs = load_existing_jobs()
        self._session_new_job_ids: set[str] = set()
        self._custom_hook = custom_hook

    def _render_table(
        self, df: pd.DataFrame, sort=True, sort_key="date_posted"
    ) -> None:
        table = self.query_one("#jobs", VimDataTable)
        table.clear(columns=True)

        if df.empty:
            table.add_column("message")
            table.add_row("No jobs available, scrape!")
            return
        else:
            if sort and sort_key in df.columns:
                df.sort_values(by=sort_key, ascending=False, inplace=True)

        for c in columns:
            table.add_column(c.name, width=c.width, key=c.name)

        self._jobs_by_id = dict()

        for _, job in df.iterrows():
            if job.get("hidden", False):
                continue
            jobid = job["id"]
            values = (str(job[c.name]) for c in columns)
            style = self._get_row_format(job)
            styled_row = (Text(v, style=style) for v in values)
            table.add_row(*styled_row, key=str(job["id"]))
            self._jobs_by_id[jobid] = job

    def _get_row_format(self, job) -> str:
        if job["id"] in self._session_new_job_ids:
            return "italic #03AC13"
        elif job["saved"]:
            return "bold #F2B705"
        return ""

    def on_mount(self) -> None:
        table = self.query_one("#jobs", VimDataTable)
        table.cursor_type = "row"
        self._render_table(self._jobs)

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )
