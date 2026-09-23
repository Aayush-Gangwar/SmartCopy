import zipfile
from pathlib import Path

from typer.testing import CliRunner

from smartcopy.cli import app

runner = CliRunner()


def test_preview_falls_back_to_gitignore(tmp_path: Path) -> None:
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "app.js").write_text("x")
    (tmp_path / ".gitignore").write_text("node_modules/\n", encoding="utf-8")

    result = runner.invoke(app, ["preview", str(tmp_path)])

    assert result.exit_code == 0
    assert "node_modules" in result.stdout
    assert "app.js" in result.stdout


def test_preview_errors_when_no_ignore_file_present(tmp_path: Path) -> None:
    (tmp_path / "app.js").write_text("x")

    result = runner.invoke(app, ["preview", str(tmp_path)])

    assert result.exit_code == 1
    assert "No .copyignore or .gitignore found" in result.stdout


def test_preview_errors_clearly_on_nonexistent_path(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist"

    result = runner.invoke(app, ["preview", str(missing)])

    assert result.exit_code == 1
    assert "not a directory" in result.stdout


def test_copy_refuses_when_dest_is_inside_src(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.js").write_text("app")
    (src / ".copyignore").write_text("node_modules\n", encoding="utf-8")

    dest = src / "backup"  # inside src - would recursively duplicate on re-copy

    result = runner.invoke(app, ["copy", str(src), str(dest), "--yes"])

    assert result.exit_code == 1
    assert "Destination" in result.stdout


def test_copy_refuses_when_dest_equals_src(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / ".copyignore").write_text("node_modules\n", encoding="utf-8")

    result = runner.invoke(app, ["copy", str(src), str(src), "--yes"])

    assert result.exit_code == 1
    assert "Destination" in result.stdout


def test_init_creates_copyignore_from_detected_preset(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")

    result = runner.invoke(app, ["init", str(tmp_path)])

    assert result.exit_code == 0
    content = (tmp_path / ".copyignore").read_text(encoding="utf-8")
    assert "node_modules" in content
    assert "node" in result.stdout


def test_init_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    (tmp_path / ".copyignore").write_text("existing\n", encoding="utf-8")

    result = runner.invoke(app, ["init", str(tmp_path)])

    assert result.exit_code == 1
    assert (tmp_path / ".copyignore").read_text(encoding="utf-8") == "existing\n"


def test_init_force_overwrites(tmp_path: Path) -> None:
    (tmp_path / ".copyignore").write_text("existing\n", encoding="utf-8")

    result = runner.invoke(app, ["init", str(tmp_path), "--preset", "python", "--force"])

    assert result.exit_code == 0
    content = (tmp_path / ".copyignore").read_text(encoding="utf-8")
    assert "venv" in content
    assert "existing" not in content


def test_stats_requires_no_ignore_file(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "app.js").write_text("x")

    result = runner.invoke(app, ["stats", str(tmp_path)])

    assert result.exit_code == 0
    assert "node_modules" in result.stdout


def test_command_copies_to_clipboard_when_available(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "node_modules").mkdir()
    (tmp_path / ".copyignore").write_text("node_modules\n", encoding="utf-8")
    monkeypatch.setattr("smartcopy.cli.pyperclip.copy", lambda text: None)

    result = runner.invoke(app, ["command", str(tmp_path), str(tmp_path / "dest")])

    assert result.exit_code == 0
    assert "node_modules" in result.stdout
    assert "Copied to clipboard" in result.stdout


def test_command_falls_back_when_clipboard_unavailable(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".copyignore").write_text("node_modules\n", encoding="utf-8")

    def _raise(text: str) -> None:
        raise RuntimeError("no clipboard")

    monkeypatch.setattr("smartcopy.cli.pyperclip.copy", _raise)

    result = runner.invoke(app, ["command", str(tmp_path), str(tmp_path / "dest")])

    assert result.exit_code == 0
    assert "copy the command above manually" in result.stdout


def test_command_warns_on_negation(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".copyignore").write_text("*.log\n!keep.log\n", encoding="utf-8")
    monkeypatch.setattr("smartcopy.cli.pyperclip.copy", lambda text: None)

    result = runner.invoke(app, ["command", str(tmp_path), str(tmp_path / "dest")])

    assert result.exit_code == 0
    assert "negation" in result.stdout.lower()


def test_zip_creates_archive_with_expected_members(tmp_path: Path) -> None:
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.js").write_text("x")
    (tmp_path / "app.js").write_text("y")
    (tmp_path / ".copyignore").write_text("node_modules\n", encoding="utf-8")

    output = tmp_path / "out.zip"
    result = runner.invoke(app, ["zip", str(tmp_path), "--output", str(output)])

    assert result.exit_code == 0
    assert output.exists()
    with zipfile.ZipFile(output) as zf:
        assert zf.namelist() == ["app.js"]


def test_verify_succeeds_for_good_copy(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.js").write_text("y")
    (src / ".copyignore").write_text("node_modules\n", encoding="utf-8")

    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "app.js").write_text("y")

    result = runner.invoke(app, ["verify", str(src), str(dest)])

    assert result.exit_code == 0
    assert "all match" in result.stdout


def test_verify_fails_for_tampered_copy(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.js").write_text("y")
    (src / ".copyignore").write_text("node_modules\n", encoding="utf-8")

    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "app.js").write_text("tampered")

    result = runner.invoke(app, ["verify", str(src), str(dest)])

    assert result.exit_code == 1
    assert "app.js" in result.stdout


def test_verify_diff_flag_shows_unified_diff(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.js").write_text("console.log('original')\n")
    (src / ".copyignore").write_text("node_modules\n", encoding="utf-8")

    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "app.js").write_text("console.log('tampered')\n")

    result = runner.invoke(app, ["verify", str(src), str(dest), "--diff"])

    assert result.exit_code == 1
    assert "--- diff: app.js ---" in result.stdout
    assert "-console.log('original')" in result.stdout
    assert "+console.log('tampered')" in result.stdout


def test_copy_without_prune_leaves_stale_excluded_folder(tmp_path: Path) -> None:
    """Reproduces the reported behavior: excluding a folder after it's
    already been copied does not remove it without --prune."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.js").write_text("app")
    (src / "node_modules").mkdir()
    (src / "node_modules" / "pkg.js").write_text("pkg")
    (src / ".copyignore").write_text("# nothing excluded yet\n", encoding="utf-8")

    dest = tmp_path / "dest"

    first = runner.invoke(app, ["copy", str(src), str(dest), "--yes"])
    assert first.exit_code == 0
    assert (dest / "node_modules" / "pkg.js").exists()

    (src / ".copyignore").write_text("node_modules\n", encoding="utf-8")

    second = runner.invoke(app, ["copy", str(src), str(dest), "--yes"])
    assert second.exit_code == 0
    assert (dest / "node_modules" / "pkg.js").exists()  # still stale, as observed


def test_copy_with_prune_removes_the_stale_excluded_folder(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.js").write_text("app")
    (src / "node_modules").mkdir()
    (src / "node_modules" / "pkg.js").write_text("pkg")
    (src / ".copyignore").write_text("# nothing excluded yet\n", encoding="utf-8")

    dest = tmp_path / "dest"

    runner.invoke(app, ["copy", str(src), str(dest), "--yes"])
    (src / ".copyignore").write_text("node_modules\n", encoding="utf-8")

    result = runner.invoke(app, ["copy", str(src), str(dest), "--yes", "--prune"], input="y\n")

    assert result.exit_code == 0
    assert not (dest / "node_modules").exists()
    assert (dest / "app.js").exists()


def test_copy_prune_reports_nothing_to_prune_when_in_sync(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.js").write_text("app")
    (src / ".copyignore").write_text("node_modules\n", encoding="utf-8")

    dest = tmp_path / "dest"

    result = runner.invoke(app, ["copy", str(src), str(dest), "--yes", "--prune"])

    assert result.exit_code == 0
    assert "Nothing to prune" in result.stdout


def test_copy_prune_declined_leaves_stale_files_in_place(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.js").write_text("app")
    (src / ".copyignore").write_text("# nothing excluded\n", encoding="utf-8")

    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "stale.txt").write_text("old")

    result = runner.invoke(app, ["copy", str(src), str(dest), "--yes", "--prune"], input="n\n")

    assert result.exit_code != 0
    assert (dest / "stale.txt").exists()
