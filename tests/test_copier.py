from pathlib import Path

from smartcopy.copier import execute
from smartcopy.ignore import IgnoreRules
from smartcopy.scanner import scan


def test_copy_creates_structure_and_reports_stats(tmp_path: Path) -> None:
    src = tmp_path / "src_proj"
    (src / "app").mkdir(parents=True)
    (src / "app" / "main.py").write_text("print('hi')")
    (src / "node_modules").mkdir()
    (src / "node_modules" / "big.txt").write_text("x" * 1000)

    rules = IgnoreRules.from_patterns(["node_modules"], case_insensitive=False)
    result = scan(src, rules)

    dest = tmp_path / "backup"
    stats = execute(result, dest, show_progress=False)

    assert (dest / "app" / "main.py").read_text() == "print('hi')"
    assert not (dest / "node_modules").exists()
    assert stats.files_copied == 1
    assert stats.dirs_skipped == 1
    assert stats.bytes_skipped >= 1000


def test_copy_merges_into_existing_destination(tmp_path: Path) -> None:
    src = tmp_path / "src_proj"
    src.mkdir()
    (src / "a.txt").write_text("new")

    dest = tmp_path / "backup"
    dest.mkdir()
    (dest / "existing.txt").write_text("keep me")
    (dest / "a.txt").write_text("old")

    rules = IgnoreRules.from_patterns([], case_insensitive=False)
    result = scan(src, rules)
    execute(result, dest, show_progress=False)

    assert (dest / "a.txt").read_text() == "new"
    assert (dest / "existing.txt").read_text() == "keep me"


def test_incremental_skips_unchanged_and_recopies_changed(tmp_path: Path) -> None:
    src = tmp_path / "src_proj"
    src.mkdir()
    (src / "unchanged.txt").write_text("same")
    (src / "changed.txt").write_text("v1")

    rules = IgnoreRules.from_patterns([])
    dest = tmp_path / "backup"

    first = execute(scan(src, rules), dest, show_progress=False)
    assert first.files_copied == 2

    (src / "changed.txt").write_text("version two, longer")

    second = execute(scan(src, rules), dest, show_progress=False, incremental=True)

    assert second.files_unchanged == 1
    assert second.files_copied == 1
    assert (dest / "changed.txt").read_text() == "version two, longer"


def test_copy_reports_failure_for_file_missing_after_scan(tmp_path: Path) -> None:
    """A file that disappears between scan and copy (locked, deleted mid-run,
    etc.) shouldn't abort the whole backup - it's skipped and reported."""
    src = tmp_path / "src_proj"
    src.mkdir()
    (src / "keep.txt").write_text("keep")
    (src / "vanishing.txt").write_text("gone soon")

    result = scan(src, IgnoreRules.from_patterns([]))
    (src / "vanishing.txt").unlink()

    dest = tmp_path / "backup"
    stats = execute(result, dest, show_progress=False)

    assert stats.files_copied == 1
    assert (dest / "keep.txt").exists()
    assert len(stats.failed) == 1
    assert stats.failed[0].path == Path("vanishing.txt")
