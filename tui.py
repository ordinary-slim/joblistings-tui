import pandas as pd
from collections import namedtuple

import yaml

from storage import load_existing_jobs, update_job_field
from fetch import load_queries
from main import search_jobs

from textual import on, work
from textual.coordinate import Coordinate
from textual.app import App, ComposeResult
from textual.widgets import Footer
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, Button, Checkbox, Label, Input, Log
from textual.validation import Number

from textual.containers import Vertical, VerticalGroup, Horizontal, HorizontalGroup

from widgets import VimDataTable, VimVerticalScroll, IntuitiveInput, VimPrinter

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
        Binding("q", "quit", "Quit"),
    ]

    def action_open_job(self) -> None:
        table = self.query_one("#jobs", VimDataTable)
        if table.cursor_row is not None:
            job_id = table.get_cell_at(Coordinate(table.cursor_row, 0))
            jobdetails = self._jobs[self._jobs["id"] == job_id].iloc[0].to_dict()
            self.push_screen(JobDetailScreen(jobdetails), callback=self._refresh_job_row)

    def _refresh_job_row(self, result):
        if result and result.get("updated"):
            updated_fields = result["updated"]
            job_id = result["job_id"]
            # Modify the in-memory DataFrame
            job_index = self._jobs.index[self._jobs["id"] == result["job_id"]][0]
            for field, value in updated_fields.items():
                self._jobs.at[job_index, field] = value
            # Re-render table row
            hidden = updated_fields.pop("hidden", False)
            table = self.query_one("#jobs", VimDataTable)
            for field in updated_fields:
                table.update_cell(row_key=job_id, column_key=field, value=str(self._jobs.at[job_index, field]))

    def action_open_scrape_menu(self) -> None:
        self.push_screen(ScrapeScreen())

    def compose(self) -> ComposeResult:
        yield Footer()
        yield VimDataTable(id="jobs")

    def __init__(self) -> None:
        super().__init__()
        self._jobs = load_existing_jobs()

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

        for _, row in df.iterrows():
            values = [row[c.name] for c in columns]
            table.add_row(*[str(v) for v in values], key=row["id"])

    # def update_cell(
    #     self,
    #     row_key: RowKey | str,
    #     column_key: ColumnKey | str,
    #     value: CellType,
    #     *,
    #     update_width: bool = False,
    # ) -> None:

    def on_mount(self) -> None:
        table = self.query_one("#jobs", VimDataTable)
        table.cursor_type = "row"
        self._render_table(self._jobs)

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )


class JobDetailScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "close", "Close"),
    ]
    # id TEXT, site TEXT, job_url TEXT, job_url_direct TEXT, title TEXT, company TEXT, location TEXT, date_posted TEXT, job_type TEXT, salary_source FLOAT, interval FLOAT, min_amount FLOAT, max_amount FLOAT, currency FLOAT, is_remote BOOLEAN, job_level FLOAT, job_function FLOAT, listing_type FLOAT, emails TEXT, description TEXT, company_industry TEXT, company_url TEXT, company_logo TEXT, company_url_direct TEXT, company_addresses TEXT, company_num_employees TEXT, company_revenue TEXT, company_description TEXT, skills FLOAT, experience_range FLOAT, company_rating FLOAT, company_reviews_count FLOAT, vacancy_count FLOAT, work_from_home_type FLOAT
    def __init__(self, job: dict) -> None:
        super().__init__()
        self.job = job
        self._updated = {}

    def compose(self) -> ComposeResult:
        with VimVerticalScroll(id="job-detail-content"):
            yield Static(f"Title: {self.job.get('title', '')}")
            yield Static(f"Company: {self.job.get('company', '')}")
            yield Static(f"Location: {self.job.get('location', '')}")
            yield Static(f"Date Posted: {self.job.get('date_posted', '')}")
            yield Static(f"Job Type: {self.job.get('job_type', '')}")
            yield Static(
                f"Salary: {self.job.get('salary_source', '')} {self.job.get('currency', '')} per {self.job.get('interval', '')}"
            )
            yield Static(f"Remote: {'Yes' if self.job.get('is_remote') else 'No'}")
            url = self.job.get('job_url_direct') or self.job.get('job_url', '')
            yield Static(f"URL: {url}")
            yield Static(f"Description:\n{self.job.get('description', '')}")
        with HorizontalGroup(id="job-actions"):
            yield Checkbox("Applied", value=self.job["applied"], id="job-details-applied")
            yield Checkbox("Hidden", value=self.job["hidden"], id="job-details-hidden")
            yield Label("Interest score", id="job-details-interest-score-label")
            yield IntuitiveInput(value=str(self.job["fit_score"]),
                                 validators=Number(0.0, 10.0, "Enter a float between 0 and 10"),
                                 max_length=4,
                                 compact=True,
                                 id="job-details-interest-score")
        yield Footer()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "job-details-applied":
            self.job["applied"] = event.value
            self._update_job_field_in_db("applied", event.value)
            self._updated["applied"] = event.value
        elif event.checkbox.id == "job-details-hidden":
            self.job["hidden"] = event.value
            self._update_job_field_in_db("hidden", event.value)
            self._updated["hidden"] = event.value

    @on(IntuitiveInput.Submitted)
    def on_fit_score_submitted(self, event: IntuitiveInput.Submitted) -> None:
        if event.validation_result is None:
            return
        if not(event.validation_result.failures):
            new_score = float(event.value)
            self.job["fit_score"] = new_score
            self._update_job_field_in_db("fit_score", new_score)
            self._updated["fit_score"] = new_score
        else:
            self.notify(f"{event.validation_result.failures[0].description}", severity="error", timeout=3)

    def _update_job_field_in_db(self, field: str, value) -> None:
        update_job_field(self.job["id"], field, value)

    def action_close(self) -> None:
        self.dismiss({"job_id": self.job["id"], "updated" : self._updated})

class ScrapeScreen(ModalScreen):
    BINDINGS = [
        Binding("s", "scrape", "Scrape", show=True),
        Binding("escape", "close", "Close", show=True),
    ]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._queries_file = "queries.yaml"
        self._all_queries = load_queries(self._queries_file)

    def compose(self) -> ComposeResult:
        with Vertical(id="scrape-dialog"):
            yield Static(f"Queries loaded from `{self._queries_file}`")

            with VimVerticalScroll(id="query-list"):
                for i, q in enumerate(self._all_queries):
                    label = f"{q['search_term']} — {q['location']}"
                    cb = Checkbox(label, value=True, id=f"query-{i}")
                    cb.data = i # Add custom attribute to store the index of the query
                    yield cb
            yield VimPrinter(id="scrape-output")
            yield Footer()

    def action_scrape(self) -> None:
        selected = [
            self._all_queries[cb.data]
            for cb in self.query("#query-list Checkbox").results(Checkbox)
            if cb.value
        ]
        self._run_scrape(selected)

    @work(thread=True, exclusive=True)
    def _run_scrape(self, queries) -> None:
        search_jobs(queries, results_wanted=10)

    def action_close(self) -> None:
        self.dismiss()

if __name__ == "__main__":
    app = JobListingsTUI()
    app.run()
