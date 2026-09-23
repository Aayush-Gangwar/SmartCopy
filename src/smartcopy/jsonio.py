from __future__ import annotations

from pathlib import Path
from typing import Any

from .copier import CopyStats
from .errors import FailedItem
from .pruner import PruneStats
from .scanner import ScanResult
from .verifier import VerifyResult
from .zipper import ZipStats


def _paths(paths: list[Path]) -> list[str]:
    return [p.as_posix() for p in paths]


def _failed(items: list[FailedItem]) -> list[dict[str, str]]:
    return [{"path": item.path.as_posix(), "error": item.error} for item in items]


def scan_result_to_dict(result: ScanResult, *, include_files: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "root": result.root.as_posix(),
        "skipped_dirs": _paths(result.skipped_dirs),
        "skipped_files": _paths(result.skipped_files),
        "skipped_symlinks": _paths(result.skipped_symlinks),
        "included_count": len(result.included_files),
        "included_size": result.included_size,
        "skipped_size": result.skipped_size,
    }
    if include_files:
        payload["included_files"] = _paths(result.included_files)
    return payload


def preview_to_dict(
    result: ScanResult, top_copy: list[str], top_skip: list[str], verbose: bool
) -> dict[str, Any]:
    payload = scan_result_to_dict(result, include_files=verbose)
    payload["top_copy"] = top_copy
    payload["top_skip"] = top_skip
    return payload


def copy_stats_to_dict(stats: CopyStats) -> dict[str, Any]:
    return {
        "files_copied": stats.files_copied,
        "bytes_copied": stats.bytes_copied,
        "dirs_skipped": stats.dirs_skipped,
        "bytes_skipped": stats.bytes_skipped,
        "files_unchanged": stats.files_unchanged,
        "bytes_saved_percent": round(stats.bytes_saved_percent, 1),
        "failed": _failed(stats.failed),
    }


def verify_result_to_dict(result: VerifyResult) -> dict[str, Any]:
    return {
        "checked": result.checked,
        "missing": _paths(result.missing),
        "size_mismatch": _paths(result.size_mismatch),
        "hash_mismatch": _paths(result.hash_mismatch),
        "failed": _failed(result.failed),
        "ok": result.ok,
    }


def zip_stats_to_dict(stats: ZipStats, output: Path) -> dict[str, Any]:
    return {
        "files_written": stats.files_written,
        "failed": _failed(stats.failed),
        "output": output.as_posix(),
    }


def prune_stats_to_dict(stats: PruneStats) -> dict[str, Any]:
    return {
        "files_removed": stats.files_removed,
        "dirs_removed": stats.dirs_removed,
        "bytes_removed": stats.bytes_removed,
        "failed": _failed(stats.failed),
    }
