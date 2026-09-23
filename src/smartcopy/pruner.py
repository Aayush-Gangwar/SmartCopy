from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .progress import progress_ticker
from .scanner import ScanResult


@dataclass
class PruneStats:
    files_removed: int = 0
    dirs_removed: int = 0
    bytes_removed: int = 0


def _is_link(path: Path) -> bool:
    return path.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(str(path)))


def _remove_path(path: Path) -> int:
    """Remove one filesystem entry, returning bytes freed (0 for directories)."""
    if _is_link(path):
        if path.is_dir():
            os.rmdir(path)  # removes the reparse point itself, not its target's contents
            return 0
        size = path.stat().st_size
        os.unlink(path)
        return size
    if path.is_dir():
        path.rmdir()  # must already be empty - callers only call this on emptied dirs
        return 0
    size = path.stat().st_size
    path.unlink()
    return size


def find_prune_files(scan_result: ScanResult, dest: Path) -> list[Path]:
    """Relative file paths present in dest but absent from the current
    included set - what --prune would remove."""
    if not dest.exists():
        return []
    included = {rel.as_posix() for rel in scan_result.included_files}
    targets: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(dest, followlinks=False):
        current_dir = Path(dirpath)
        for name in filenames:
            rel = (current_dir / name).relative_to(dest)
            if rel.as_posix() not in included:
                targets.append(rel)
    return targets


def prune(scan_result: ScanResult, dest: Path, show_progress: bool = True) -> PruneStats:
    """True-mirror prune: after this, dest contains nothing that isn't in
    scan_result.included_files - same idea as robocopy /MIR or rsync
    --delete. This deletes real files; callers must confirm with the user
    before calling it."""
    stats = PruneStats()
    if not dest.exists():
        return stats

    targets = find_prune_files(scan_result, dest)
    with progress_ticker(len(targets), show_progress, "Pruning") as tick:
        for rel in targets:
            stats.bytes_removed += _remove_path(dest / rel)
            stats.files_removed += 1
            tick()

    # Bottom-up: remove stray symlinked/junction directories outright (the
    # scanner never includes symlinks, so any found here are always stale),
    # then remove directories left empty by everything removed above.
    for dirpath, dirnames, _filenames in os.walk(dest, topdown=False, followlinks=False):
        current_dir = Path(dirpath)
        for name in list(dirnames):
            sub = current_dir / name
            if _is_link(sub):
                _remove_path(sub)
                stats.dirs_removed += 1

        if current_dir == dest:
            continue
        try:
            if not any(current_dir.iterdir()):
                _remove_path(current_dir)
                stats.dirs_removed += 1
        except OSError:
            pass

    return stats
