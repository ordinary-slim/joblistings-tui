import pandas as pd
from collections import namedtuple
from rich.text import Text

import pyperclip

from joblistings_tui.backend.storage import load_existing_jobs

from textual.coordinate import Coordinate
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer


from .widgets import VimDataTable

from .job_description import JobDetailScreen
from .scrape_menu import ScrapeScreen

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
        Binding("d", "toggle_dark", "Toggle dark mode"),
        Binding("s", "open_scrape_menu", "Open scrape menu"),
        Binding("o", "open_job", "Open job details"),
        Binding("y", "yank_job_url", "Copy job URL"),
        Binding("q", "quit", "Quit"),
    ]

    def action_open_job(self) -> None:
        table = self.query_one("#jobs", VimDataTable)
        if table.cursor_row is not None:
            job_id = table.get_cell_at(Coordinate(table.cursor_row, 0)).plain
            jobdetails = self._jobs[self._jobs["id"] == job_id].iloc[0].to_dict()
            self.push_screen(
                JobDetailScreen(jobdetails), callback=self._refresh_job_row
            )

    def action_yank_job_url(self) -> None:
        table = self.query_one("#jobs", VimDataTable)
        if table.cursor_row is None:
            return
        job_id = table.get_cell_at(Coordinate(table.cursor_row, 0)).plain
        job = self._jobs_by_id[job_id]
        url = job["job_url_direct"] or job["job_url"]
        pyperclip.copy(url)
        self.notify(
            f"URL copied for job: {job['title']} at {job['company']}",
            timeout=3,
            severity="information",
        )

    def _refresh_job_row(self, result):
        if result and result.get("updated"):
            updated_fields = result["updated"]
            job_id = result["job_id"]
            # Modify the in-memory DataFrame
            job_index = self._jobs.index[self._jobs["id"] == result["job_id"]][0]
            for field, value in updated_fields.items():
                self._jobs.at[job_index, field] = value
            # Re-render table row
            table = self.query_one("#jobs", VimDataTable)
            hidden = updated_fields.pop("hidden", False)
            if hidden:
                table.remove_row(job_id)
            else:
                visible_columns = {c.name for c in columns}
                for field in updated_fields:
                    if field in visible_columns:
                        cell = table.get_cell(row_key=job_id, column_key=field)
                        cell.plain = str(self._jobs.at[job_index, field])
                        table.update_cell(
                            row_key=job_id,
                            column_key=field,
                            value=cell,
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

    def __init__(self) -> None:
        super().__init__()
        self._jobs = load_existing_jobs()
        self._session_new_job_ids: set[str] = set()

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

        for _, row in df.iterrows():
            if row.get("hidden", False):
                continue
            jobid = row["id"]
            values = (str(row[c.name]) for c in columns)
            style = "italic #03AC13" if jobid in self._session_new_job_ids else ""
            styled_row = (Text(v, style=style) for v in values) 
            table.add_row(*styled_row, key=str(row["id"]))
            self._jobs_by_id[jobid] = row

    def on_mount(self) -> None:
        table = self.query_one("#jobs", VimDataTable)
        table.cursor_type = "row"
        self._render_table(self._jobs)

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )
