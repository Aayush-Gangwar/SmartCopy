import zipfile
from pathlib import Path

from smartcopy.ignore import IgnoreRules
from smartcopy.scanner import scan
from smartcopy.zipper import create_zip


def test_zip_contains_exactly_the_included_files(tmp_path: Path) -> None:
    src = tmp_path / "proj"
    (src / "app").mkdir(parents=True)
    (src / "app" / "main.py").write_text("print('hi')")
    (src / "node_modules").mkdir()
    (src / "node_modules" / "big.txt").write_text("x")

    rules = IgnoreRules.from_patterns(["node_modules"])
    result = scan(src, rules)

    output = tmp_path / "out.zip"
    stats = create_zip(result, output, show_progress=False)

    assert stats.files_written == 1
    assert stats.failed == []
    with zipfile.ZipFile(output) as zf:
        names = set(zf.namelist())
        assert names == {"app/main.py"}
        assert zf.read("app/main.py") == b"print('hi')"


def test_zip_reports_failure_for_file_vanished_after_scan(tmp_path: Path) -> None:
    src = tmp_path / "proj"
    src.mkdir()
    (src / "keep.txt").write_text("keep")
    (src / "vanish.txt").write_text("gone")

    result = scan(src, IgnoreRules.from_patterns([]))
    (src / "vanish.txt").unlink()

    output = tmp_path / "out.zip"
    stats = create_zip(result, output, show_progress=False)

    assert stats.files_written == 1
    assert len(stats.failed) == 1
    assert stats.failed[0].path == Path("vanish.txt")
