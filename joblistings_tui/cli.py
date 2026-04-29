import argparse
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Callable

from joblistings_tui.tui.main_screen import JobListingsTUI


def _load_custom_hook(script_file: str) -> Callable[[dict], str | None]:
    script_path = Path(script_file).expanduser().resolve()
    if not script_path.is_file():
        raise ValueError(f"Script file does not exist: {script_path}")

    spec = importlib.util.spec_from_file_location(
        "joblistings_tui_custom_hook", script_path
    )
    if spec is None or spec.loader is None:
        raise ValueError(f"Unable to import script file: {script_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    hook = getattr(module, "main", None)
    if not callable(hook):
        raise ValueError(
            f"Script file must expose callable `main(job: dict)`: {script_path}"
        )
    return hook


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the job listings TUI.")
    parser.add_argument(
        "--script-file",
        type=str,
        default="",
        help="Path to a Python file exposing `main(job: dict)` for custom hook on 'c'.",
    )
    args = parser.parse_args()

    custom_hook = None
    if args.script_file:
        custom_hook = _load_custom_hook(args.script_file)

    app = JobListingsTUI(custom_hook=custom_hook)
    app.run()
