import pandas as pd

from storage import load_existing_jobs

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer
from textual.containers import HorizontalGroup, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Button, Digits, Footer, Header, DataTable


class JobListingsTUI(App):
    """A Textual app to display job listings."""

    CSS_PATH = "tui.tcss"
    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
    ]

    def action_toggle_dark(self) -> None:
            """An action to toggle dark mode."""
            self.theme = ("textual-dark" if self.theme == "textual-light" else "textual-light")

    def compose(self) -> ComposeResult:
        yield Footer()
        yield DataTable(id="jobs")

    def __init__(self) -> None:
        super().__init__()
        self._jobs = load_existing_jobs()

    def _render_table(self, df: pd.DataFrame) -> None:
        table = self.query_one("#jobs", DataTable)
        table.clear(columns=True)

        if df.empty:
            table.add_column("message")
            table.add_row("No jobs available. Try Run Scrape.")
            return

        columns = [
            "id",
            "title",
            "company",
            "location",
        ]
        for col in columns:
            table.add_column(col)

        for _, row in df.iterrows():
            values = [row.get(col, "") or "" for col in columns]
            table.add_row(*[str(v) for v in values])

    def on_mount(self) -> None:
        table = self.query_one("#jobs", DataTable)
        table.cursor_type = "row"
        self._render_table(self._jobs)

if __name__ == "__main__":
    app = JobListingsTUI()
    app.run()
