from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from .progress import progress_ticker
from .scanner import ScanResult

_CHUNK_SIZE = 1024 * 1024


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class VerifyResult:
    checked: int = 0
    missing: list[Path] = field(default_factory=list)
    size_mismatch: list[Path] = field(default_factory=list)
    hash_mismatch: list[Path] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.missing or self.size_mismatch or self.hash_mismatch)


def verify(scan_result: ScanResult, dest: Path, show_progress: bool = True) -> VerifyResult:
    result = VerifyResult()
    with progress_ticker(len(scan_result.included_files), show_progress, "Verifying") as tick:
        for rel in scan_result.included_files:
            result.checked += 1
            src_path = scan_result.root / rel
            dest_path = dest / rel
            if not dest_path.exists():
                result.missing.append(rel)
            elif src_path.stat().st_size != dest_path.stat().st_size:
                result.size_mismatch.append(rel)
            elif _hash_file(src_path) != _hash_file(dest_path):
                result.hash_mismatch.append(rel)
            tick()
    return result
