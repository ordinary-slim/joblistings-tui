from textual import events
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Input, RichLog
from textual.binding import Binding

class VimDataTable(DataTable):
    BINDINGS = [
        Binding("h", "cursor_left", "Left", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("l", "cursor_right", "Right", show=False),
        Binding("g", "scroll_top", "First Line", show=False),
        Binding("G", "scroll_bottom", "Last Line", show=False),
        Binding("0", "scroll_home", "Line Start", show=False),
        Binding("$", "scroll_end", "Line End", show=False),
        Binding("u", "page_up", "Page up", show=False),
        Binding("d", "page_down", "Page down", show=False),
    ]

class VimVerticalScroll(VerticalScroll):
    BINDINGS = [
        Binding("k", "scroll_up", "Scroll Up", show=False),
        Binding("j", "scroll_down", "Scroll Down", show=False),
        Binding("h", "scroll_left", "Scroll Left", show=False),
        Binding("l", "scroll_right", "Scroll Right", show=False),
        Binding("0", "scroll_home", "Scroll Home", show=False),
        Binding("$", "scroll_end", "Scroll End", show=False),
        Binding("u", "page_up", "Page Up", show=False),
        Binding("d", "page_down", "Page Down", show=False),
    ]

class IntuitiveInput(Input):
    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
        Binding("enter", "submit", "Submit", show=True),
    ]

    def action_close(self) -> None:
        close = getattr(self.screen, "action_close", None)
        if close is not None:
            close()
        else:
            self.screen.dismiss()

class VimPrinter(RichLog):
    """A subclass of textual's RichLog which captures and displays all print calls."""
    BINDINGS = [
        Binding("k", "scroll_up", "Scroll Up", show=False),
        Binding("j", "scroll_down", "Scroll Down", show=False),
        Binding("h", "scroll_left", "Scroll Left", show=False),
        Binding("l", "scroll_right", "Scroll Right", show=False),
        Binding("0", "scroll_home", "Scroll Home", show=False),
        Binding("$", "scroll_end", "Scroll End", show=False),
        Binding("u", "page_up", "Page Up", show=False),
        Binding("d", "page_down", "Page Down", show=False),
        # Binding("ctrl+pageup", "page_left", "Page Left", show=False),
        # Binding("ctrl+pagedown", "page_right", "Page Right", show=False),
    ]

    def on_mount(self) -> None:
        self.wrap = True
        self.markup = True
        self.begin_capture_print()

    def on_print(self, event: events.Print) -> None:
        if (text := event.text) != "\n":
            self.write(text.rstrip().replace("DEBUG", "[red]DEBUG[/]"))
