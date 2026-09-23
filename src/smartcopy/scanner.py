from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .ignore import IgnoreRules

COPYIGNORE_FILENAME = ".copyignore"


@dataclass
class ScanResult:
    root: Path
    included_files: list[Path] = field(default_factory=list)
    skipped_dirs: list[Path] = field(default_factory=list)
    skipped_files: list[Path] = field(default_factory=list)
    skipped_symlinks: list[Path] = field(default_factory=list)
    included_size: int = 0
    skipped_size: int = 0


def _has_isjunction() -> bool:
    return hasattr(os.path, "isjunction")


def _is_symlink_like(entry: "os.DirEntry[str]") -> bool:
    if entry.is_symlink():
        return True
    return _has_isjunction() and os.path.isjunction(entry.path)


def _path_is_symlink_like(path: str) -> bool:
    if os.path.islink(path):
        return True
    return _has_isjunction() and os.path.isjunction(path)


def _dir_size(path: Path) -> int:
    # Read-only stat pass to report bytes saved. Cheaper than copying, but not
    # free on very large trees - a known MVP tradeoff, not optimized further.
    total = 0
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        dirnames[:] = [d for d in dirnames if not _path_is_symlink_like(os.path.join(dirpath, d))]
        for name in filenames:
            file_path = os.path.join(dirpath, name)
            if _path_is_symlink_like(file_path):
                continue
            try:
                total += os.path.getsize(file_path)
            except OSError:
                pass
    return total


def scan(root: Path, rules: IgnoreRules) -> ScanResult:
    root = root.resolve()
    result = ScanResult(root=root)
    _walk(root, root, rules, result)
    return result


def _walk(root: Path, current: Path, rules: IgnoreRules, result: ScanResult) -> None:
    try:
        entries = list(os.scandir(current))
    except OSError:
        return

    for entry in entries:
        if entry.name == COPYIGNORE_FILENAME:
            continue

        rel = Path(entry.path).relative_to(root)

        if _is_symlink_like(entry):
            result.skipped_symlinks.append(rel)
            continue

        if entry.is_dir(follow_symlinks=False):
            if rules.matches(entry.name, rel.as_posix()):
                result.skipped_dirs.append(rel)
                result.skipped_size += _dir_size(Path(entry.path))
                continue
            _walk(root, Path(entry.path), rules, result)
        elif entry.is_file(follow_symlinks=False):
            try:
                size = entry.stat(follow_symlinks=False).st_size
            except OSError:
                size = 0
            if rules.matches(entry.name, rel.as_posix()):
                result.skipped_files.append(rel)
                result.skipped_size += size
                continue
            result.included_files.append(rel)
            result.included_size += size


def top_level(root: Path, rules: IgnoreRules) -> tuple[list[str], list[str]]:
    copy_names: list[str] = []
    skip_names: list[str] = []
    try:
        entries = sorted(os.scandir(root), key=lambda e: e.name.lower())
    except OSError:
        return copy_names, skip_names

    for entry in entries:
        if entry.name == COPYIGNORE_FILENAME:
            continue
        is_dir = entry.is_dir(follow_symlinks=False)
        label = entry.name + ("/" if is_dir else "")
        if _is_symlink_like(entry):
            skip_names.append(f"{label} (symlink)")
            continue
        if rules.matches(entry.name):
            skip_names.append(label)
            continue
        copy_names.append(label)
    return copy_names, skip_names
