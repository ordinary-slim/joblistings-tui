import pandas as pd

import yaml

from storage import load_existing_jobs
from fetch import load_queries
from main import search_jobs

from textual.coordinate import Coordinate
from textual.app import App, ComposeResult
from textual.widgets import Footer
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, Button

from textual.containers import HorizontalGroup

from widgets import VimDataTable, VimVerticalScroll

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
            jobdetails = self._jobs[self._jobs["id"] == job_id]
            job = jobdetails.iloc[0].to_dict()
            self.push_screen(JobDetailScreen(job))

    def action_open_scrape_menu(self) -> None:
        self.push_screen(ScrapeScreen())

    def compose(self) -> ComposeResult:
        yield Footer()
        yield VimDataTable(id="jobs")

    def __init__(self) -> None:
        super().__init__()
        self._jobs = load_existing_jobs()

    def _render_table(self, df: pd.DataFrame, sort=True, sort_key="date_posted") -> None:
        table = self.query_one("#jobs", VimDataTable)
        table.clear(columns=True)

        if df.empty:
            table.add_column("message")
            table.add_row("No jobs available, scrape!")
            return
        else:
            if sort and sort_key in df.columns:
                df.sort_values(by=sort_key, ascending=False, inplace=True)

        columns = [
            "id",
            "title",
            "company",
            "location",
            "date_posted",
        ]
        widths = [0, 60, 30, 20, 15]
        for col, width in zip(columns, widths):
            table.add_column(col, width=width)

        for _, row in df.iterrows():
            values = [row.get(col, "") or "" for col in columns]
            table.add_row(*[str(v) for v in values])

    def on_mount(self) -> None:
        table = self.query_one("#jobs", VimDataTable)
        table.cursor_type = "row"
        self._render_table(self._jobs)

    def action_toggle_dark(self) -> None:
            """An action to toggle dark mode."""
            self.theme = ("textual-dark" if self.theme == "textual-light" else "textual-light")

class JobDetailScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "close", "Escape"),
    ]
    # id TEXT, site TEXT, job_url TEXT, job_url_direct TEXT, title TEXT, company TEXT, location TEXT, date_posted TEXT, job_type TEXT, salary_source FLOAT, interval FLOAT, min_amount FLOAT, max_amount FLOAT, currency FLOAT, is_remote BOOLEAN, job_level FLOAT, job_function FLOAT, listing_type FLOAT, emails TEXT, description TEXT, company_industry TEXT, company_url TEXT, company_logo TEXT, company_url_direct TEXT, company_addresses TEXT, company_num_employees TEXT, company_revenue TEXT, company_description TEXT, skills FLOAT, experience_range FLOAT, company_rating FLOAT, company_reviews_count FLOAT, vacancy_count FLOAT, work_from_home_type FLOAT
    def __init__(self, job: dict) -> None:
        super().__init__()
        self.job = job

    def compose(self) -> ComposeResult:
        with VimVerticalScroll():
            yield Static(f"Title: {self.job.get('title', '')}")
            yield Static(f"Company: {self.job.get('company', '')}")
            yield Static(f"Location: {self.job.get('location', '')}")
            yield Static(f"Date Posted: {self.job.get('date_posted', '')}")
            yield Static(f"Job Type: {self.job.get('job_type', '')}")
            yield Static(f"Salary: {self.job.get('salary_source', '')} {self.job.get('currency', '')} per {self.job.get('interval', '')}")
            yield Static(f"Remote: {'Yes' if self.job.get('is_remote') else 'No'}")
            url = self.job.get('job_url_direct') or self.job.get('job_url', '')
            yield Static(f"URL: {url}")
            yield Static(f"Description:\n{self.job.get('description', '')}")
            yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close":
            self.dismiss()

    def action_close(self) -> None:
        self.dismiss()

class ScrapeScreen(ModalScreen):
    def __init__(self):
        super().__init__()
        self._queries_file = "queries.yaml"
        self._queries = load_queries(self._queries_file)

    def compose(self) -> ComposeResult:
        with VimVerticalScroll():
            yield Static(f"Queries loaded from {self._queries_file}:")
            for q in self._queries:
                yield Static(f"Search Term: {q['search_term']}, Location: {q['location']}")

        with HorizontalGroup():
            yield Button("Scrape", id="scrape")
            yield Button("Cancel", id="close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "scrape":
            search_jobs(self._queries, results_wanted=20)
            self.dismiss()
        elif event.button.id == "close":
            self.dismiss()

    def action_close(self) -> None:
        self.dismiss()

if __name__ == "__main__":
    app = JobListingsTUI()
    app.run()
