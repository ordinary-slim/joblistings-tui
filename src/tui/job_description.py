from typing import Union, Sequence

import pyperclip

from src.backend.storage import update_job_fields
from src.backend.fit_score import score_job

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Footer, Static, Checkbox, Label
from textual.validation import Number
from textual.worker import Worker, WorkerState
from textual.reactive import reactive

from textual.containers import (
    HorizontalGroup,
)

from .widgets import VimVerticalScroll, IntuitiveInput

class JobDetailScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("y", "yank", "Copy URL"),
        Binding("s", "score", "LLM-score"),
    ]

    fit_keywords = reactive("")
    fit_reasoning = reactive("")

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
            self.url = self.job.get("job_url_direct") or self.job.get("job_url", "")
            yield Static(f"URL: {self.url}")

            yield Static(id="fit-keywords")
            yield Static(id="fit-reasoning")

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

    def on_mount(self) -> None:
        self.fit_keywords = self.job["fit_keywords"]
        self.fit_reasoning = self.job["fit_reasoning"]

    def watch_fit_keywords(self, value):
        self.query_one("#fit-keywords", Static).update(f"Fit Keywords: {value}")
        # self._updated = {"fit_keywords": value}

    def watch_fit_reasoning(self, value):
        self.query_one("#fit-reasoning", Static).update(f"Fit Reasoning:\n{value}")
        # self._updated = {"fit_reasoning": value}

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "job-details-applied":
            self.job["applied"] = event.value
            self._update_job_fields_in_db("applied", event.value)
            self._updated["applied"] = event.value
        elif event.checkbox.id == "job-details-hidden":
            self.job["hidden"] = event.value
            self._update_job_fields_in_db("hidden", event.value)
            self._updated["hidden"] = event.value

    def action_yank(self) -> None:
        pyperclip.copy(self.url)
        self.notify("URL copied.", timeout=3, severity="information")

    def action_score(self, verbose=True) -> None:
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
            if result is None:
                self.notify(
                    "LLM scoring returned no result.", timeout=5, severity="error"
                )
                return
            new_score, keywords, reasoning = (
                result["score"],
                result["keywords"],
                result["reasoning"],
            )
            self.fit_keywords, self.fit_reasoning = keywords, reasoning
            self.query_one("#job-details-interest-score", IntuitiveInput).value = str(
                new_score
            )
            if new_score:
                self.job["fit_score"] = new_score
                self.job["fit_keywords"] = keywords
                self.job["fit_reasoning"] = reasoning
                self._update_job_fields_in_db(
                    ["fit_score", "fit_keywords", "fit_reasoning"],
                    [new_score, keywords, reasoning],
                )
                self._updated["fit_score"] = new_score
                self._updated["fit_keywords"] = keywords
                self._updated["fit_reasoning"] = reasoning
                self.notify(
                    f"LLM fit score: {new_score}\nKeywords: {keywords}\nReasoning: {reasoning}",
                    timeout=5,
                    severity="information",
                )
            else:
                self.notify(
                    f"LLM scoring failed. Reasoning: {reasoning}",
                    timeout=5,
                    severity="error",
                )

    @on(IntuitiveInput.Submitted)
    def on_fit_score_submitted(self, event: IntuitiveInput.Submitted) -> None:
        if event.validation_result is None:
            return
        if not (event.validation_result.failures):
            new_score = float(event.value)
            self.job["fit_score"] = new_score
            self._update_job_fields_in_db("fit_score", new_score)
            self._updated["fit_score"] = new_score
        else:
            self.notify(
                f"{event.validation_result.failures[0].description}",
                severity="error",
                timeout=3,
            )

    def _update_job_fields_in_db(
        self,
        fields: Union[str, Sequence[str]],
        values: Union[float, bool, str, Sequence[Union[float, bool, str]]],
    ) -> None:
        update_job_fields(self.job["id"], fields, values)

    def action_close(self) -> None:
        self.dismiss({"job_id": self.job["id"], "updated": self._updated})


