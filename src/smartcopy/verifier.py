from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from .progress import progress_ticker
from .scanner import ScanResult

_CHUNK_SIZE = 1024 * 1024
_MAX_DIFF_LINES = 40


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _looks_binary(path: Path, sample_size: int = 8192) -> bool:
    # Same heuristic git uses: a NUL byte anywhere in a leading sample means
    # binary. Valid UTF-8 text never contains a raw NUL.
    with path.open("rb") as f:
        return b"\x00" in f.read(sample_size)


def diff_text(a: Path, b: Path, max_lines: int = _MAX_DIFF_LINES) -> str:
    """Unified diff for text files; a plain size comparison for binary ones
    (diffing binary content line-by-line isn't meaningful)."""
    if _looks_binary(a) or _looks_binary(b):
        return f"Binary files differ ({a.stat().st_size} bytes vs {b.stat().st_size} bytes)"

    try:
        a_lines = a.read_text(encoding="utf-8").splitlines(keepends=True)
        b_lines = b.read_text(encoding="utf-8").splitlines(keepends=True)
    except (UnicodeDecodeError, OSError):
        return f"Binary files differ ({a.stat().st_size} bytes vs {b.stat().st_size} bytes)"

    diff_lines = list(difflib.unified_diff(a_lines, b_lines, fromfile=str(a), tofile=str(b)))
    if not diff_lines:
        return "(no textual difference)"

    truncated = diff_lines[:max_lines]
    text = "".join(truncated)
    if len(diff_lines) > max_lines:
        text += f"... ({len(diff_lines) - max_lines} more diff lines not shown)\n"
    return text


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
