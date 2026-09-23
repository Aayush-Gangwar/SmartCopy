from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .errors import FailedItem
from .progress import ProgressCallback, progress_ticker
from .scanner import ScanResult


@dataclass
class PruneStats:
    files_removed: int = 0
    dirs_removed: int = 0
    bytes_removed: int = 0
    failed: list[FailedItem] = field(default_factory=list)


def _is_link(path: Path) -> bool:
    return path.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(str(path)))


def _remove_path(path: Path) -> int:
    """Remove one filesystem entry, returning bytes freed (0 for directories
    and for any symlink/junction, since removing a link never frees the
    space used by its target)."""
    if _is_link(path):
        if path.is_dir():
            # Directory symlink/junction. On Windows, RemoveDirectory (what
            # os.rmdir maps to) removes just the reparse point without
            # touching the target. On POSIX there's no such distinction -
            # rmdir() on a symlink follows it and tries to remove the
            # target itself (failing with ENOTEMPTY if it's not empty), so
            # unlink() - which always removes the link entry itself - is
            # what's needed there instead.
            if os.name == "nt":
                os.rmdir(path)
            else:
                os.unlink(path)
            return 0
        os.unlink(path)
        return 0
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


def prune(
    scan_result: ScanResult,
    dest: Path,
    show_progress: bool = True,
    on_progress: Optional[ProgressCallback] = None,
) -> PruneStats:
    """True-mirror prune: after this, dest contains nothing that isn't in
    scan_result.included_files - same idea as robocopy /MIR or rsync
    --delete. This deletes real files; callers must confirm with the user
    before calling it."""
    stats = PruneStats()
    if not dest.exists():
        return stats

    targets = find_prune_files(scan_result, dest)
    with progress_ticker(len(targets), show_progress, "Pruning", on_progress) as tick:
        for rel in targets:
            try:
                stats.bytes_removed += _remove_path(dest / rel)
                stats.files_removed += 1
            except OSError as exc:
                # A locked/permission-denied file stays put rather than
                # aborting the whole prune - reported, not silently skipped.
                stats.failed.append(FailedItem(path=rel, error=str(exc)))
            tick()

    # Bottom-up: remove stray symlinked/junction directories outright (the
    # scanner never includes symlinks, so any found here are always stale),
    # then remove directories left empty by everything removed above. A
    # parent is only checked once its children have already been handled.
    for dirpath, dirnames, _filenames in os.walk(dest, topdown=False, followlinks=False):
        current_dir = Path(dirpath)
        for name in list(dirnames):
            sub = current_dir / name
            if _is_link(sub):
                try:
                    _remove_path(sub)
                    stats.dirs_removed += 1
                except OSError as exc:
                    stats.failed.append(FailedItem(path=sub.relative_to(dest), error=str(exc)))

        if current_dir == dest:
            continue
        try:
            # os.listdir fully materializes the listing in one call, unlike
            # iterdir()'s generator, which any() would otherwise abandon
            # half-read the moment it finds a first entry.
            if not os.listdir(current_dir):
                _remove_path(current_dir)
                stats.dirs_removed += 1
        except OSError:
            # Not empty (a file in it failed to delete above, so it must
            # stay) or a transient access issue - a leftover empty-ish
            # directory isn't data loss, so it's not worth escalating.
            pass

    return stats
