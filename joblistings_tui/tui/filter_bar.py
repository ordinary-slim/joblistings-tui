from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Static

from .widgets import IntuitiveInput


class FilterBar(ModalScreen):
    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
    ]

    def __init__(self, query: str = "") -> None:
        super().__init__()
        self._query = query

    def compose(self) -> ComposeResult:
        with Vertical(id="filter-query-dialog"):
            yield Static("Filter query", classes="section-title")
            yield IntuitiveInput(
                value=self._query,
                id="filter-query-input",
                placeholder="company:stripe is:saved fit_score:>=0.7 -intern",
            )
            yield Footer()

    def on_mount(self) -> None:
        self.query_one("#filter-query-input", IntuitiveInput).focus()

    @on(IntuitiveInput.Submitted)
    def on_query_submitted(self, event: IntuitiveInput.Submitted) -> None:
        self.dismiss(event.value.strip())

    def action_close(self) -> None:
        self.dismiss(None)
