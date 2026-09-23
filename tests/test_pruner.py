import os
import stat
from pathlib import Path

import pytest

from smartcopy.ignore import IgnoreRules
from smartcopy.pruner import find_prune_files, prune
from smartcopy.scanner import scan


def _scan(src: Path, *ignored: str):
    return scan(src, IgnoreRules.from_patterns(list(ignored)))


def test_find_prune_files_identifies_stale_entries(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.js").write_text("app")

    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "app.js").write_text("app")
    (dest / "stale.txt").write_text("old")

    targets = find_prune_files(_scan(src), dest)

    assert targets == [Path("stale.txt")]


def test_prune_removes_stale_files_and_now_empty_directory(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.js").write_text("app")

    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "app.js").write_text("app")
    (dest / "node_modules").mkdir()
    (dest / "node_modules" / "pkg.js").write_text("stale package")

    stats = prune(_scan(src), dest, show_progress=False)

    assert (dest / "app.js").exists()
    assert not (dest / "node_modules").exists()
    assert stats.files_removed == 1
    assert stats.dirs_removed == 1
    assert stats.bytes_removed > 0


def test_prune_keeps_directory_that_still_has_an_included_file(tmp_path: Path) -> None:
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "sub" / "keep.js").write_text("keep")

    dest = tmp_path / "dest"
    (dest / "sub").mkdir(parents=True)
    (dest / "sub" / "keep.js").write_text("keep")
    (dest / "sub" / "stale.js").write_text("stale")

    stats = prune(_scan(src), dest, show_progress=False)

    assert (dest / "sub").exists()
    assert (dest / "sub" / "keep.js").exists()
    assert not (dest / "sub" / "stale.js").exists()
    assert stats.files_removed == 1
    assert stats.dirs_removed == 0


def test_prune_removes_stray_symlinked_directory(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.js").write_text("app")

    real_dir = tmp_path / "real"
    real_dir.mkdir()
    (real_dir / "file.txt").write_text("data")

    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "app.js").write_text("app")
    link = dest / "stray_link"
    try:
        link.symlink_to(real_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted on this system")

    stats = prune(_scan(src), dest, show_progress=False)

    assert not link.exists()
    assert real_dir.exists()  # the symlink's target is untouched
    assert stats.dirs_removed == 1


def test_nothing_to_prune_when_destination_matches(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.js").write_text("app")

    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "app.js").write_text("app")

    assert find_prune_files(_scan(src), dest) == []

    stats = prune(_scan(src), dest, show_progress=False)
    assert stats.files_removed == 0
    assert stats.dirs_removed == 0


def test_prune_reports_failure_for_undeletable_file(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "keep.txt").write_text("keep")

    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "keep.txt").write_text("keep")
    stale = dest / "stale.txt"
    stale.write_text("stale")
    os.chmod(stale, stat.S_IREAD)

    try:
        stats = prune(_scan(src), dest, show_progress=False)
    finally:
        # Restore so tmp_path cleanup can remove it - but only if it's still
        # there. On POSIX, deletability is governed by the containing
        # directory's write permission, not the file's own mode, so the
        # delete below may have actually succeeded despite chmod.
        if stale.exists():
            os.chmod(stale, stat.S_IWRITE)

    if stale.exists():
        assert len(stats.failed) == 1
        assert stats.failed[0].path == Path("stale.txt")
    else:
        pytest.skip("this OS allows deleting read-only files - failure path not exercised here")
