import pandas as pd
from collections import namedtuple

import yaml

from storage import load_existing_jobs, update_job_field
from fetch import load_queries, ALL_JOB_SITES, DEFAULT_JOB_SITES, JOB_SITE_LABELS
from main import search_jobs
from fit_score import score_job

from textual import on, work
from textual.coordinate import Coordinate
from textual.app import App, ComposeResult
from textual.widgets import Footer
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, Button, Checkbox, Label, Input, Log
from textual.validation import Number, Integer
from textual.worker import Worker, WorkerState

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
            self.push_screen(
                JobDetailScreen(jobdetails), callback=self._refresh_job_row
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
            hidden = updated_fields.pop("hidden", False)
            table = self.query_one("#jobs", VimDataTable)
            for field in updated_fields:
                table.update_cell(
                    row_key=job_id,
                    column_key=field,
                    value=str(self._jobs.at[job_index, field]),
                )

    def action_open_scrape_menu(self) -> None:
        self.push_screen(ScrapeScreen(), callback=self._refresh_after_scrape)

    def _refresh_after_scrape(self, result) -> None:
        if not result:
            return
        new_jobs = result["new_jobs"]
        if new_jobs.empty:
            return
        self._jobs = pd.concat([self._jobs, new_jobs], ignore_index=True)
        self._render_table(self._jobs)

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
        Binding("s",  "score", "LLM-score"),
    ]

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
            url = self.job.get("job_url_direct") or self.job.get("job_url", "")
            yield Static(f"URL: {url}")
            yield Static(f"Description:\n{self.job.get('description', '')}")
        with HorizontalGroup(id="job-actions"):
            yield Checkbox(
                "Applied", value=self.job["applied"], id="job-details-applied"
            )
            yield Checkbox("Hidden", value=self.job["hidden"], id="job-details-hidden")
            yield Label("Fit score", id="job-details-interest-score-label")
            yield IntuitiveInput(
                value=str(self.job["fit_score"]),
                validators=Number(0.0, 10.0, "Enter a float between 0 and 10"),
                max_length=4,
                compact=True,
                id="job-details-interest-score",
            )
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

    def action_score(self, verbose = True) -> None:
        if verbose:
            self.notify("Scoring job with LLM...", timeout=5, severity="information")
        self._score_job_with_llm()

    @work(thread=True, exclusive=True)
    def _score_job_with_llm(self) -> dict:
        return score_job(self.job)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Called when the worker state changes."""
        if event.state == WorkerState.SUCCESS:
            result = event.worker.result
            new_score, keywords, reasoning = result["score"], result["keywords"], result["reasoning"]
            self.query_one("#job-details-interest-score", IntuitiveInput).value = str(new_score)
            if new_score:
                self.job["fit_score"] = new_score
                self._update_job_field_in_db("fit_score", new_score)
                self._updated["fit_score"] = new_score
                self.notify(f"LLM fit score: {new_score}\nKeywords: {keywords}\nReasoning: {reasoning}", timeout=5, severity="information")
            else:
                self.notify(f"LLM scoring failed. Reasoning: {reasoning}", timeout=5, severity="error")

    @on(IntuitiveInput.Submitted)
    def on_fit_score_submitted(self, event: IntuitiveInput.Submitted) -> None:
        if event.validation_result is None:
            return
        if not (event.validation_result.failures):
            new_score = float(event.value)
            self.job["fit_score"] = new_score
            self._update_job_field_in_db("fit_score", new_score)
            self._updated["fit_score"] = new_score
        else:
            self.notify(
                f"{event.validation_result.failures[0].description}",
                severity="error",
                timeout=3,
            )

    def _update_job_field_in_db(self, field: str, value) -> None:
        update_job_field(self.job["id"], field, value)

    def action_close(self) -> None:
        self.dismiss({"job_id": self.job["id"], "updated": self._updated})


class ScrapeScreen(ModalScreen):
    BINDINGS = [
        Binding("s", "scrape", "Scrape", show=True),
        Binding("escape", "close", "Close", show=True),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._queries_file = "queries.yaml"
        self._all_queries = load_queries(self._queries_file)
        self._scrape_result = {"new_jobs": pd.DataFrame()}

    def compose(self) -> ComposeResult:
        with Vertical(id="scrape-dialog"):
            yield Static(f"Queries loaded from `{self._queries_file}`")
            with Horizontal(id="scrape-top"):
                with VimVerticalScroll(id="query-list"):
                    for i, q in enumerate(self._all_queries):
                        label = f"{q['search_term']} — {q['location']}"
                        yield Checkbox(label, value=True, id=f"query-{i}")

                with Vertical(id="settings-pane"):
                    yield Static("Scrape settings", classes="pane-title")

                    yield Static("Job sites", classes="section-title")
                    with VimVerticalScroll(id="site-list"):
                        for site_key in ALL_JOB_SITES:
                            yield Checkbox(
                                JOB_SITE_LABELS[site_key],
                                value=(site_key in DEFAULT_JOB_SITES),
                                id=f"site-{site_key}",
                            )

                    yield Static("Results per query and site", classes="section-title")
                    yield IntuitiveInput(
                        value="10",
                        validators=Integer(
                            minimum=1, failure_description="Enter a number >= 1"
                        ),
                        max_length=4,
                        compact=True,
                        id="results-per-query-site",
                    )

            yield VimPrinter(id="scrape-output")
            yield Footer()

    def action_scrape(self) -> None:
        selected = [
            self._all_queries[int(cb.id.split("-")[1])]
            for cb in self.query("#query-list Checkbox").results(Checkbox)
            if cb.value and cb.id
        ]
        results_wanted = self.query_one("#results-per-query-site", IntuitiveInput)
        jobsites = [
            site_key
            for site_key in ALL_JOB_SITES
            if self.query_one(f"#site-{site_key}", Checkbox).value
        ]
        self._run_scrape(selected, jobsites, results_wanted=int(results_wanted.value))

    @work(thread=True, exclusive=True)
    def _run_scrape(self, queries, jobsites, results_wanted) -> None:
        new_jobs = search_jobs(
            queries, jobsites=jobsites, results_wanted=results_wanted
        )
        self._scrape_result = {
            "new_jobs": pd.concat([self._scrape_result["new_jobs"],
                                   new_jobs], ignore_index=True)}

    def action_close(self) -> None:
        self.dismiss(self._scrape_result)

if __name__ == "__main__":
    app = JobListingsTUI()
    app.run()
