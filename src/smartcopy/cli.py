from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from .copier import execute
from .ignore import IgnoreRules
from .report import console, render_copy_summary, render_preview
from .scanner import scan, top_level

app = typer.Typer(help="CTRL+A for developers - copy source, skip dependencies.")


def _load_rules(root: Path, ignore_file: Optional[Path]) -> IgnoreRules:
    path = ignore_file or (root / ".copyignore")
    if not path.is_file():
        console.print(f"[red]No .copyignore found at {path}. Use --ignore-file to point at one.[/red]")
        raise typer.Exit(code=1)
    return IgnoreRules.load(path)


@app.command()
def preview(
    path: Path = typer.Argument(Path("."), help="Project root to scan."),
    ignore_file: Optional[Path] = typer.Option(None, "--ignore-file", help="Path to a .copyignore file."),
    verbose: bool = typer.Option(False, "--verbose", help="List every file that will be copied."),
) -> None:
    root = path.resolve()
    rules = _load_rules(root, ignore_file)
    result = scan(root, rules)
    top_copy, top_skip = top_level(root, rules)
    render_preview(result, top_copy, top_skip, verbose)


@app.command()
def copy(
    src: Path = typer.Argument(..., help="Project root to copy from."),
    dest: Path = typer.Argument(..., help="Destination directory."),
    ignore_file: Optional[Path] = typer.Option(None, "--ignore-file", help="Path to a .copyignore file."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
) -> None:
    root = src.resolve()
    dest_root = dest.resolve()
    rules = _load_rules(root, ignore_file)
    result = scan(root, rules)

    if not yes:
        typer.confirm(
            f"Copy {len(result.included_files)} files from {root} to {dest_root}?",
            abort=True,
        )

    stats = execute(result, dest_root)
    render_copy_summary(stats)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
