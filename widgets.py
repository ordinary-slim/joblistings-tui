from textual.widgets import DataTable
from textual.binding import Binding

class VimDataTable(DataTable):

    BINDINGS = [
        Binding("h", "go_left", "Left", show=False),
        Binding("j", "go_down", "Down", show=False),
        Binding("k", "go_up", "Up", show=False),
        Binding("l", "go_right", "Right", show=False),
        Binding("g", "scroll_top", "First Line", show=False),
        Binding("G", "scroll_bottom", "Last Line", show=False),
        Binding("0", "scroll_home", "Line Start", show=False),
        Binding("$", "scroll_end", "Line End", show=False),
    ]

    def action_go_left(self) -> None:
        self.action_cursor_left()

    def action_go_down(self) -> None:
        self.action_cursor_down()

    def action_go_up(self) -> None:
        self.action_cursor_up()

    def action_go_right(self) -> None:
        self.action_cursor_right()

    def action_scroll_top(self) -> None:
        super().action_scroll_top()

    def action_scroll_bottom(self) -> None:
        super().action_scroll_bottom()

    def action_scroll_home(self) -> None:
        super().action_scroll_home()

    def action_scroll_end(self) -> None:
        super().action_scroll_end()
