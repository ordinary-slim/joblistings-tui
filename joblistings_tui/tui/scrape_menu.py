import pandas as pd

from joblistings_tui.backend.fetch import load_queries, ALL_JOB_SITES, DEFAULT_JOB_SITES, JOB_SITE_LABELS
from joblistings_tui.backend.main import search_jobs

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Footer, Static, Checkbox, Label
from textual.validation import Integer

from textual.containers import (
    Vertical,
    Horizontal,
    Grid,
)

from .widgets import VimVerticalScroll, IntuitiveInput, VimPrinter
from joblistings_tui.config import QUERIES_FILE

class ScrapeScreen(ModalScreen):
    BINDINGS = [
        Binding("s", "scrape", "Scrape", show=True),
        Binding("escape", "close", "Close", show=True),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._queries_file = QUERIES_FILE
        self._all_queries = load_queries(self._queries_file)
        self._scrape_result = {"new_jobs": pd.DataFrame()}

    def compose(self) -> ComposeResult:
        with Vertical(id="scrape-dialog"):
            with Horizontal(id="scrape-top"):
                with VimVerticalScroll(id="query-list"):
                    # yield Static(f"Queries loaded from `{self._queries_file}`")
                    # for i, q in enumerate(self._all_queries):
                    #     label = f"{q['search_term']} — {q['location']}"
                    #     yield Checkbox(label, value=True, id=f"query-{i}")
                    yield Static("Search:", id="search-bar-header")
                    with Horizontal(id="search-bar"):
                        yield IntuitiveInput(
                            placeholder="software developper",
                            id="search-terms-input",
                            max_length=50,
                        )
                        yield IntuitiveInput(
                            placeholder="Barcelona, Spain",
                            id="search-location-input",
                            max_length=30,
                        )

                    yield Static("Job sites", classes="section-title")
                    with Grid(id="jobsites-grid"):
                        for site_key in ALL_JOB_SITES:
                            yield Checkbox(
                                JOB_SITE_LABELS[site_key],
                                value=(site_key in DEFAULT_JOB_SITES),
                                id=f"site-{site_key}",
                            )

                with Vertical(id="settings-pane"):
                    yield Static("Scrape settings", classes="pane-title")

                    yield Label("Results per query and site:")
                    yield IntuitiveInput(
                        value="10",
                        validators=Integer(
                            minimum=1, failure_description="Enter a number >= 1"
                        ),
                        max_length=4,
                        compact=True,
                        id="results-per-query-site",
                    )
                    # Checkbox for "Score with LLM"
                    yield Checkbox(
                        "Score with LLM",
                        value=True,
                        id="scrape-score-with-llm",
                    )

            yield VimPrinter(id="scrape-output")
            yield Footer()

    def action_scrape(self) -> None:
        # selected = [
        #     self._all_queries[int(cb.id.split("-")[1])]
        #     for cb in self.query("#query-list Checkbox").results(Checkbox)
        #     if cb.value and cb.id
        # ]
        query = {
                "search_term" : self.query_one("#search-terms-input", IntuitiveInput).value,
                "location" : self.query_one("#search-location-input", IntuitiveInput).value,
        }
        results_wanted = int(
            self.query_one("#results-per-query-site", IntuitiveInput).value
        )
        score = self.query_one("#scrape-score-with-llm", Checkbox).value
        jobsites = [
            site_key
            for site_key in ALL_JOB_SITES
            if self.query_one(f"#site-{site_key}", Checkbox).value
        ]
        self._run_scrape([query], jobsites, score, results_wanted)

    @work(thread=True, exclusive=True)
    def _run_scrape(self, queries, jobsites, score, results_wanted) -> None:
        new_jobs = search_jobs(
            queries,
            jobsites=jobsites,
            score=score,
            results_wanted=results_wanted,
        )
        self._scrape_result = {
            "new_jobs": pd.concat(
                [self._scrape_result["new_jobs"], new_jobs], ignore_index=True
            )
        }

    def action_close(self) -> None:
        self.dismiss(self._scrape_result)
