from __future__ import annotations

from contextlib import contextmanager

from rich.progress import BarColumn, Progress, TextColumn


@contextmanager
def progress_ticker(total: int, show_progress: bool, label: str = "Working"):
    """Yields a zero-arg tick() function to call once per unit of work."""
    if not show_progress or total == 0:
        yield lambda: None
        return
    with Progress(
        TextColumn(label),
        BarColumn(),
        TextColumn("{task.completed}/{task.total} files"),
    ) as progress:
        task = progress.add_task(label, total=total)
        yield lambda: progress.advance(task)
