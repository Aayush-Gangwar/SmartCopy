from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .scanner import ScanResult


@dataclass
class CopyStats:
    files_copied: int
    bytes_copied: int
    dirs_skipped: int
    bytes_skipped: int

    @property
    def bytes_saved_percent(self) -> float:
        total = self.bytes_copied + self.bytes_skipped
        return (self.bytes_skipped / total * 100) if total else 0.0


def execute(scan_result: ScanResult, dest: Path) -> CopyStats:
    dest.mkdir(parents=True, exist_ok=True)
    bytes_copied = 0
    files_copied = 0
    for rel in scan_result.included_files:
        src_path = scan_result.root / rel
        dest_path = dest / rel
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest_path)
        files_copied += 1
        bytes_copied += dest_path.stat().st_size

    return CopyStats(
        files_copied=files_copied,
        bytes_copied=bytes_copied,
        dirs_skipped=len(scan_result.skipped_dirs),
        bytes_skipped=scan_result.skipped_size,
    )
