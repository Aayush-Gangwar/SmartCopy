from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .errors import FailedItem
from .progress import progress_ticker
from .scanner import ScanResult


@dataclass
class ZipStats:
    files_written: int = 0
    failed: list[FailedItem] = field(default_factory=list)


def create_zip(scan_result: ScanResult, output: Path, show_progress: bool = True) -> ZipStats:
    stats = ZipStats()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        with progress_ticker(len(scan_result.included_files), show_progress, "Zipping") as tick:
            for rel in scan_result.included_files:
                try:
                    zf.write(scan_result.root / rel, arcname=rel.as_posix())
                    stats.files_written += 1
                except OSError as exc:
                    stats.failed.append(FailedItem(path=rel, error=str(exc)))
                tick()
    return stats
