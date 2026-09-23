from pathlib import Path

from smartcopy.ignore import IgnoreRules
from smartcopy.scanner import scan
from smartcopy.verifier import diff_text, verify


def _scan_all(src: Path):
    return scan(src, IgnoreRules.from_patterns([]))


def test_verify_ok_for_identical_copy(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("hello")

    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "a.txt").write_text("hello")

    result = verify(_scan_all(src), dest, show_progress=False)

    assert result.ok
    assert result.checked == 1


def test_verify_reports_missing_file(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("hello")

    dest = tmp_path / "dest"
    dest.mkdir()

    result = verify(_scan_all(src), dest, show_progress=False)

    assert not result.ok
    assert Path("a.txt") in result.missing


def test_verify_reports_size_mismatch(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("hello world")

    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "a.txt").write_text("hi")

    result = verify(_scan_all(src), dest, show_progress=False)

    assert not result.ok
    assert Path("a.txt") in result.size_mismatch


def test_verify_reports_hash_mismatch_for_same_size_different_content(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("hello")

    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "a.txt").write_text("olleh")

    result = verify(_scan_all(src), dest, show_progress=False)

    assert not result.ok
    assert Path("a.txt") in result.hash_mismatch


def test_verify_reports_failed_for_source_file_vanished_after_scan(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("hello")

    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "a.txt").write_text("hello")

    result = _scan_all(src)
    (src / "a.txt").unlink()  # vanished between scan and verify

    outcome = verify(result, dest, show_progress=False)

    assert not outcome.ok
    assert len(outcome.failed) == 1
    assert outcome.failed[0].path == Path("a.txt")


def test_diff_text_shows_unified_diff_for_text_files(tmp_path: Path) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("line1\nline2\nline3\n")
    b.write_text("line1\nCHANGED\nline3\n")

    diff = diff_text(a, b)

    assert "-line2" in diff
    assert "+CHANGED" in diff


def test_diff_text_reports_binary_files_by_size(tmp_path: Path) -> None:
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"\x00\x01\x02")
    b.write_bytes(b"\x00\x01\x02\x03\x04")

    diff = diff_text(a, b)

    assert "Binary files differ" in diff
    assert "3 bytes" in diff
    assert "5 bytes" in diff
