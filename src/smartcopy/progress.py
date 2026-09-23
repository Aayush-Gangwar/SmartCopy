from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Optional

from rich.progress import BarColumn, Progress, TextColumn

ProgressCallback = Callable[[int, int], None]


@contextmanager
def progress_ticker(
    total: int,
    show_progress: bool,
    label: str = "Working",
    on_progress: Optional[ProgressCallback] = None,
):
    """Yields a zero-arg tick() function to call once per unit of work.

    - on_progress, if given, takes priority: tick() calls it with
      (completed, total), throttled to roughly 100 updates regardless of
      total size so a huge tree doesn't flood the caller with events.
    - Otherwise falls back to a Rich progress bar (show_progress=True) or
      a no-op (show_progress=False) - the original terminal behavior.
    """
    if on_progress is not None:
        step = max(1, total // 100) if total else 1
        completed = 0
        on_progress(completed, total)

        def tick() -> None:
            nonlocal completed
            completed += 1
            if completed % step == 0 or completed == total:
                on_progress(completed, total)

        yield tick
        return

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
