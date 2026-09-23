from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from .copier import execute
from .ignore import IgnoreRules
from .presets import PRESETS, default_patterns, detect_presets
from .report import console, render_copy_summary, render_preview, render_stats, render_zip_summary
from .scanner import scan, top_level
from .zipper import create_zip

app = typer.Typer(help="CTRL+A for developers - copy source, skip dependencies.")


def _load_rules(root: Path, ignore_file: Optional[Path]) -> IgnoreRules:
    if ignore_file:
        if not ignore_file.is_file():
            console.print(f"[red]No ignore file found at {ignore_file}.[/red]")
            raise typer.Exit(code=1)
        return IgnoreRules.load(ignore_file)

    copyignore = root / ".copyignore"
    if copyignore.is_file():
        return IgnoreRules.load(copyignore)

    gitignore = root / ".gitignore"
    if gitignore.is_file():
        console.print(f"[yellow]No .copyignore found - using {gitignore} instead.[/yellow]")
        return IgnoreRules.load(gitignore)

    console.print(
        f"[red]No .copyignore or .gitignore found in {root}. "
        f"Use --ignore-file, or run 'smartcopy init' to create one.[/red]"
    )
    raise typer.Exit(code=1)


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


def _resolve_src_dest(paths: list[Path]) -> tuple[Path, Path]:
    if len(paths) == 1:
        return Path("."), paths[0]
    if len(paths) == 2:
        return paths[0], paths[1]
    console.print("[red]Usage: [SRC] DEST[/red]")
    raise typer.Exit(code=1)


@app.command()
def copy(
    paths: list[Path] = typer.Argument(
        ..., help="[SRC] DEST - SRC defaults to the current directory when omitted."
    ),
    ignore_file: Optional[Path] = typer.Option(None, "--ignore-file", help="Path to a .copyignore file."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
) -> None:
    src, dest = _resolve_src_dest(paths)
    root = src.resolve()
    dest_root = dest.resolve()
    rules = _load_rules(root, ignore_file)
    result = scan(root, rules)

    if not yes:
        typer.confirm(
            f"Copy {len(result.included_files)} files from {root} to {dest_root}?",
            abort=True,
        )

    stats = execute(result, dest_root, show_progress=True)
    render_copy_summary(stats)


@app.command(name="zip")
def zip_cmd(
    path: Path = typer.Argument(Path("."), help="Project root to zip."),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output .zip path (default: <project-name>-clean.zip next to the project)."
    ),
    ignore_file: Optional[Path] = typer.Option(None, "--ignore-file", help="Path to a .copyignore file."),
) -> None:
    root = path.resolve()
    rules = _load_rules(root, ignore_file)
    result = scan(root, rules)
    out = (output or root.parent / f"{root.name}-clean.zip").resolve()
    zip_stats = create_zip(result, out, show_progress=True)
    render_zip_summary(zip_stats, out)


@app.command()
def stats(path: Path = typer.Argument(Path("."), help="Project root to analyze.")) -> None:
    """Zero-config bloat report - no .copyignore required."""
    root = path.resolve()
    preset_names = detect_presets(root)
    rules = IgnoreRules.from_patterns(default_patterns(root))
    result = scan(root, rules)
    render_stats(result, preset_names)


@app.command()
def init(
    path: Path = typer.Argument(Path("."), help="Project root to create a .copyignore in."),
    preset: Optional[str] = typer.Option(
        None, "--preset", help=f"One of: {', '.join(PRESETS)}. Auto-detected from the project if omitted."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing .copyignore."),
) -> None:
    root = path.resolve()
    target = root / ".copyignore"
    if target.exists() and not force:
        console.print(f"[red]{target} already exists. Use --force to overwrite.[/red]")
        raise typer.Exit(code=1)

    if preset:
        if preset not in PRESETS:
            console.print(f"[red]Unknown preset '{preset}'. Choose from: {', '.join(PRESETS)}[/red]")
            raise typer.Exit(code=1)
        keys = [preset]
    else:
        keys = detect_presets(root)

    patterns: list[str] = []
    for key in keys:
        patterns.extend(PRESETS[key])
    patterns = list(dict.fromkeys(patterns))

    target.write_text("\n".join(patterns) + "\n", encoding="utf-8")
    console.print(f"[green]Created {target}[/green] using preset(s): {', '.join(keys)}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
