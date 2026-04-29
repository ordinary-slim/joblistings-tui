from typing import Callable, Union, Sequence

import pyperclip

from joblistings_tui.backend.storage import update_job_fields
from joblistings_tui.backend.fit_score import score_job

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
        Binding("y", "yank_url", "Copy URL"),
        Binding("Y", "yank_description", "Copy description"),
        Binding("s", "score", "LLM-score"),
        Binding("c", "run_user_hook", "Run user script"),
    ]

    fit_keywords = reactive("")
    fit_reasoning = reactive("")

    def __init__(
        self,
        job: dict,
        custom_hook: Callable[[dict], str | None] | None = None,
    ) -> None:
        super().__init__()
        self.job = job
        self._updated = {}
        self._custom_hook = custom_hook

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
            yield Checkbox("Saved", value=self.job["saved"], id="job-details-saved")
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
        checkbox_id_to_field = {
            "job-details-applied": "applied",
            "job-details-hidden": "hidden",
            "job-details-saved": "saved",
        }
        if event.checkbox.id is None:
            return
        key = checkbox_id_to_field.get(event.checkbox.id)
        if key is not None:
            self.job[key] = event.value
            self._update_job_fields_in_db(key, event.value)
            self._updated[key] = event.value

    def action_yank_url(self) -> None:
        pyperclip.copy(self.url)
        self.notify("URL copied.", timeout=2, severity="information")

    def action_yank_description(self) -> None:
        description = "\n".join(
            [
                f"Title: {self.job.get('title', '')}",
                f"Company: {self.job.get('company', '')}",
                f"Location: {self.job.get('location', '')}",
                f"Date Posted: {self.job.get('date_posted', '')}",
                f"Job Type: {self.job.get('job_type', '')}",
                f"Salary: {self.job.get('salary_source', '')} {self.job.get('currency', '')} per {self.job.get('interval', '')}",
                f"Remote: {'Yes' if self.job.get('is_remote') else 'No'}",
                f"URL: {self.url}",
                f"Description:\n{self.job.get('description', '')}",
                f"Fit score (1-10): {self.job.get('fit_score', '')}",
                f"Fit keywords: {self.job.get('fit_keywords', '')}",
            ]
        )
        pyperclip.copy(description)
        self.notify("Description copied.", timeout=2, severity="information")

    def action_score(self, verbose=True) -> None:
        if verbose:
            self.notify("Scoring job with LLM...", timeout=5, severity="information")
        self._score_job_with_llm()

    def action_run_user_hook(self) -> None:
        if self._custom_hook is None:
            return
        log = self._custom_hook(self.job)
        if log:
            self.notify(log, timeout=10, severity="information")

    @work(thread=True, exclusive=True)
    def _score_job_with_llm(self) -> dict:
        def status_callback(message: str) -> None:
            self.app.call_from_thread(
                self.notify,
                message,
                timeout=6,
                severity="warning",
            )

        return score_job(self.job, status_callback=status_callback)

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
                if "timeout" in reasoning.lower() or "timed out" in reasoning.lower():
                    self.notify(
                        "LLM request timed out. Try again or reduce model latency.",
                        timeout=6,
                        severity="error",
                    )
                self.notify(
                    f"LLM scoring failed. Reasoning: {reasoning}",
                    timeout=5,
                    severity="error",
                )
        elif event.state == WorkerState.ERROR:
            error = event.worker.error
            message = str(error) if error else "Unknown worker error"
            if "timeout" in message.lower() or "timed out" in message.lower():
                self.notify(
                    f"LLM request timed out: {message}",
                    timeout=6,
                    severity="error",
                )
            else:
                self.notify(
                    f"LLM scoring failed: {message}",
                    timeout=6,
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
