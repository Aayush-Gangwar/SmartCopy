from __future__ import annotations

from rich.console import Console

from .copier import CopyStats
from .scanner import ScanResult
from .zipper import ZipStats

console = Console()


def _human_size(num_bytes: float) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def render_preview(
    result: ScanResult,
    top_copy: list[str],
    top_skip: list[str],
    verbose: bool,
) -> None:
    console.print("[bold green]Will Copy[/bold green]")
    for name in top_copy:
        console.print(f"  {name}")
    console.print()

    console.print("[bold red]Will Skip[/bold red]")
    skipped_paths = sorted(result.skipped_dirs + result.skipped_files, key=lambda p: p.as_posix())
    for rel in skipped_paths:
        console.print(f"  [red]{rel.as_posix()}[/red]")
    console.print()

    if verbose:
        console.print("[bold]Files that will be copied[/bold]")
        for rel in sorted(result.included_files, key=lambda p: p.as_posix()):
            console.print(f"  {rel.as_posix()}")
        console.print()

    total = result.included_size + result.skipped_size
    saved_pct = (result.skipped_size / total * 100) if total else 0.0
    console.print(
        f"[green]{len(result.included_files)} files[/green] "
        f"([bold]{_human_size(result.included_size)}[/bold]) will be copied  -  "
        f"[red]{len(skipped_paths)} skipped[/red] "
        f"([bold]{_human_size(result.skipped_size)}[/bold] saved, {saved_pct:.1f}%)"
    )


def render_zip_summary(stats: ZipStats, output: Path) -> None:
    console.print(f"[green]Wrote {stats.files_written} files to {output}[/green]")


def render_stats(result: ScanResult, preset_names: list[str]) -> None:
    console.print(f"[bold]Zero-config scan using built-in defaults:[/bold] {', '.join(preset_names)}")
    console.print()

    skipped_paths = sorted(result.skipped_dirs + result.skipped_files, key=lambda p: p.as_posix())
    if skipped_paths:
        console.print("[bold red]Bloat found[/bold red]")
        for rel in skipped_paths:
            console.print(f"  [red]{rel.as_posix()}[/red]")
        console.print()

    total = result.included_size + result.skipped_size
    saved_pct = (result.skipped_size / total * 100) if total else 0.0
    console.print(
        f"[bold]{_human_size(result.skipped_size)}[/bold] of generated/dependency bloat found "
        f"out of {_human_size(total)} total ({saved_pct:.1f}%)."
    )


def render_copy_summary(stats: CopyStats) -> None:
    console.print(
        f"[green]Copied {stats.files_copied} files[/green] "
        f"([bold]{_human_size(stats.bytes_copied)}[/bold])"
    )
    if stats.files_unchanged:
        console.print(f"[cyan]{stats.files_unchanged} files unchanged, skipped[/cyan]")
    console.print(f"[red]Skipped {stats.dirs_skipped} directories[/red]")
    console.print(
        f"[bold]Saved {_human_size(stats.bytes_skipped)} "
        f"({stats.bytes_saved_percent:.1f}%)[/bold]"
    )
