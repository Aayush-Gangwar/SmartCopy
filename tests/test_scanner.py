from pathlib import Path

import pytest

from smartcopy.ignore import IgnoreRules
from smartcopy.scanner import scan, top_level


def _make_rules(*patterns: str) -> IgnoreRules:
    return IgnoreRules.from_patterns(patterns)


def test_prunes_nested_ignored_dirs_at_any_depth(tmp_path: Path) -> None:
    (tmp_path / "frontend" / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "frontend" / "node_modules" / "pkg" / "index.js").write_text("x")
    (tmp_path / "frontend" / "src").mkdir(parents=True)
    (tmp_path / "frontend" / "src" / "app.js").write_text("y")
    (tmp_path / "packages" / "a" / "node_modules").mkdir(parents=True)
    (tmp_path / "packages" / "a" / "node_modules" / "dep.js").write_text("z")

    result = scan(tmp_path, _make_rules("node_modules"))

    included = {p.as_posix() for p in result.included_files}
    skipped = {p.as_posix() for p in result.skipped_dirs}

    assert "frontend/src/app.js" in included
    assert "frontend/node_modules" in skipped
    assert "packages/a/node_modules" in skipped
    assert not any("node_modules" in p for p in included)


def test_symlinked_directory_is_skipped_not_followed(tmp_path: Path) -> None:
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    (real_dir / "file.txt").write_text("data")
    link = tmp_path / "link"
    try:
        link.symlink_to(real_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted on this system")

    result = scan(tmp_path, _make_rules())

    assert any(p.as_posix() == "link" for p in result.skipped_symlinks)
    assert not any(p.as_posix().startswith("link/") for p in result.included_files)


def test_ignored_file_name_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "keep.txt").write_text("a")
    (tmp_path / "drop.log").write_text("b")

    result = scan(tmp_path, _make_rules("drop.log"))

    included = {p.as_posix() for p in result.included_files}
    skipped_files = {p.as_posix() for p in result.skipped_files}

    assert "keep.txt" in included
    assert "drop.log" in skipped_files


def test_top_level_categorizes_immediate_children(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "node_modules").mkdir()

    copy_names, skip_names = top_level(tmp_path, _make_rules("node_modules"))

    assert "src/" in copy_names
    assert "node_modules/" in skip_names
