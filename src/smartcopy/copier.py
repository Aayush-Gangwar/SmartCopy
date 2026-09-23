from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .errors import FailedItem
from .progress import progress_ticker
from .scanner import ScanResult


@dataclass
class CopyStats:
    files_copied: int
    bytes_copied: int
    dirs_skipped: int
    bytes_skipped: int
    files_unchanged: int = 0
    failed: list[FailedItem] = field(default_factory=list)

    @property
    def bytes_saved_percent(self) -> float:
        total = self.bytes_copied + self.bytes_skipped
        return (self.bytes_skipped / total * 100) if total else 0.0


def _is_unchanged(src_path: Path, dest_path: Path) -> bool:
    if not dest_path.exists():
        return False
    try:
        src_stat = src_path.stat()
        dest_stat = dest_path.stat()
    except OSError:
        return False
    # Truncated to whole seconds - some filesystems (FAT32) only store mtime
    # with 2-second resolution, so sub-second differences aren't meaningful.
    return src_stat.st_size == dest_stat.st_size and int(src_stat.st_mtime) <= int(dest_stat.st_mtime)


def execute(
    scan_result: ScanResult, dest: Path, show_progress: bool = True, incremental: bool = False
) -> CopyStats:
    dest.mkdir(parents=True, exist_ok=True)
    bytes_copied = 0
    files_copied = 0
    files_unchanged = 0
    failed: list[FailedItem] = []
    with progress_ticker(len(scan_result.included_files), show_progress, "Copying") as tick:
        for rel in scan_result.included_files:
            src_path = scan_result.root / rel
            dest_path = dest / rel
            try:
                if incremental and _is_unchanged(src_path, dest_path):
                    files_unchanged += 1
                    continue
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dest_path)
                files_copied += 1
                bytes_copied += dest_path.stat().st_size
            except OSError as exc:
                # A locked/permission-denied file shouldn't abort the whole
                # backup - skip it, report it, and keep going.
                failed.append(FailedItem(path=rel, error=str(exc)))
            finally:
                tick()

    return CopyStats(
        files_copied=files_copied,
        bytes_copied=bytes_copied,
        dirs_skipped=len(scan_result.skipped_dirs),
        bytes_skipped=scan_result.skipped_size,
        files_unchanged=files_unchanged,
        failed=failed,
    )
