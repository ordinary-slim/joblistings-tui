import pandas as pd

from joblistings_tui.backend.fetch import (
    load_queries,
    ALL_JOB_SITES,
    DEFAULT_JOB_SITES,
    JOB_SITE_LABELS,
)
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
        Binding("S", "pick_boards", "Select job sites", show=True),
        Binding("escape", "close", "Close", show=True),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._queries_file = QUERIES_FILE
        self._all_queries = load_queries(self._queries_file)
        self._selected_sites = list(DEFAULT_JOB_SITES)
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
                    yield Static(id="selected-sites-summary")

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
                        value=False,
                        id="scrape-score-with-llm",
                    )

            yield VimPrinter(id="scrape-output")
            yield Footer()

    def on_mount(self) -> None:
        self._refresh_sites_summary()

    def _refresh_sites_summary(self) -> None:
        summary = self.query_one("#selected-sites-summary", Static)
        labels = [JOB_SITE_LABELS[site] for site in self._selected_sites]
        if labels:
            summary.update("Selected: " + ", ".join(labels))
        else:
            summary.update("Selected: none")

    def action_pick_boards(self) -> None:
        self.app.push_screen(
            JobBoardsScreen(
                selected_sites=self._selected_sites,
            ),
            self._on_sites_picked,
        )

    def _on_sites_picked(self, result: list[str] | None) -> None:
        if result is not None:
            self._selected_sites = result
            self._refresh_sites_summary()

    def action_scrape(self) -> None:
        # selected = [
        #     self._all_queries[int(cb.id.split("-")[1])]
        #     for cb in self.query("#query-list Checkbox").results(Checkbox)
        #     if cb.value and cb.id
        # ]
        query = {
            "search_term": self.query_one("#search-terms-input", IntuitiveInput).value,
            "location": self.query_one("#search-location-input", IntuitiveInput).value,
        }
        results_wanted = int(
            self.query_one("#results-per-query-site", IntuitiveInput).value
        )
        score = self.query_one("#scrape-score-with-llm", Checkbox).value
        jobsites = self._selected_sites
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


class JobBoardsScreen(ModalScreen):
    BINDINGS = [
        Binding("enter", "apply", "Apply", show=True),
        Binding("a", "select_all", "All", show=True),
        Binding("n", "select_none", "None", show=True),
        Binding("escape", "close", "Close", show=True),
    ]

    def __init__(self, selected_sites: list[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._selected_sites = set(selected_sites)

    def compose(self) -> ComposeResult:
        with Vertical(id="jobsites-dialog"):
            yield Static("Select job sites", classes="section-title")
            with Grid(id="jobsites-grid"):
                for site_key in ALL_JOB_SITES:
                    yield Checkbox(
                        JOB_SITE_LABELS[site_key],
                        value=(site_key in self._selected_sites),
                        id=f"site-{site_key}",
                    )
            yield Footer()

    def _get_selected_sites(self) -> list[str]:
        return [
            site_key
            for site_key in ALL_JOB_SITES
            if self.query_one(f"#site-{site_key}", Checkbox).value
        ]

    def action_apply(self) -> None:
        self.dismiss(self._get_selected_sites())

    def action_select_all(self) -> None:
        for site_key in ALL_JOB_SITES:
            self.query_one(f"#site-{site_key}", Checkbox).value = True

    def action_select_none(self) -> None:
        for site_key in ALL_JOB_SITES:
            self.query_one(f"#site-{site_key}", Checkbox).value = False

    def action_close(self) -> None:
        self.dismiss(self._get_selected_sites())
