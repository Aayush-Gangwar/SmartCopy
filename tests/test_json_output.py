import json
from pathlib import Path

from typer.testing import CliRunner

from smartcopy.cli import app

runner = CliRunner()


def _events(stdout: str) -> list[dict]:
    return [json.loads(line) for line in stdout.splitlines() if line.strip()]


def _final(stdout: str) -> dict:
    """The last NDJSON line - always the terminal "result" or "error" event,
    with any number of "progress" events possibly preceding it."""
    return _events(stdout)[-1]


def _make_project(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    (src / "node_modules").mkdir(parents=True)
    (src / "node_modules" / "pkg.js").write_text("pkg")
    (src / "app.js").write_text("app")
    (src / ".copyignore").write_text("node_modules\n", encoding="utf-8")
    return src


def test_preview_json_is_valid_and_shaped(tmp_path: Path) -> None:
    src = _make_project(tmp_path)

    result = runner.invoke(app, ["preview", str(src), "--json"])

    assert result.exit_code == 0
    event = _final(result.stdout)
    assert event["event"] == "result"
    payload = event["data"]
    assert payload["skipped_dirs"] == ["node_modules"]
    assert payload["top_copy"] == ["app.js"]
    assert payload["top_skip"] == ["node_modules/"]
    assert "included_files" not in payload  # only present with --verbose
    assert isinstance(payload["included_size"], int)


def test_preview_json_compare_dest_reports_would_prune(tmp_path: Path) -> None:
    src = _make_project(tmp_path)
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "app.js").write_text("app")
    (dest / "stale.txt").write_text("stale")

    result = runner.invoke(app, ["preview", str(src), "--json", "--compare-dest", str(dest)])

    payload = _final(result.stdout)["data"]
    assert payload["would_prune"] == ["stale.txt"]


def test_preview_json_without_compare_dest_omits_would_prune(tmp_path: Path) -> None:
    src = _make_project(tmp_path)

    result = runner.invoke(app, ["preview", str(src), "--json"])

    payload = _final(result.stdout)["data"]
    assert "would_prune" not in payload


def test_preview_json_verbose_includes_file_list(tmp_path: Path) -> None:
    src = _make_project(tmp_path)

    result = runner.invoke(app, ["preview", str(src), "--json", "--verbose"])

    payload = _final(result.stdout)["data"]
    assert payload["included_files"] == ["app.js"]


def test_preview_json_error_path_is_still_valid_json(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist"

    result = runner.invoke(app, ["preview", str(missing), "--json"])

    assert result.exit_code == 1
    event = _final(result.stdout)
    assert event["event"] == "error"
    assert "message" in event


def test_copy_json_requires_yes(tmp_path: Path) -> None:
    src = _make_project(tmp_path)
    dest = tmp_path / "dest"

    result = runner.invoke(app, ["copy", str(src), str(dest), "--json"])

    assert result.exit_code == 1
    event = _final(result.stdout)
    assert event["event"] == "error"


def test_copy_json_streams_progress_then_result(tmp_path: Path) -> None:
    src = _make_project(tmp_path)
    dest = tmp_path / "dest"

    result = runner.invoke(app, ["copy", str(src), str(dest), "--json", "--yes"])

    events = _events(result.stdout)
    assert events[-1]["event"] == "result"
    progress_events = [e for e in events if e["event"] == "progress"]
    assert len(progress_events) >= 1
    assert progress_events[0]["label"] == "Copying"
    assert progress_events[-1]["completed"] == progress_events[-1]["total"]


def test_copy_json_reports_stats(tmp_path: Path) -> None:
    src = _make_project(tmp_path)
    dest = tmp_path / "dest"

    result = runner.invoke(app, ["copy", str(src), str(dest), "--json", "--yes"])

    assert result.exit_code == 0
    payload = _final(result.stdout)["data"]
    assert payload["files_copied"] == 1
    assert payload["failed"] == []
    assert payload["prune"] is None


def test_copy_json_with_prune_requires_yes_prune(tmp_path: Path) -> None:
    src = _make_project(tmp_path)
    dest = tmp_path / "dest"
    runner.invoke(app, ["copy", str(src), str(dest), "--json", "--yes"])

    result = runner.invoke(app, ["copy", str(src), str(dest), "--json", "--yes", "--prune"])

    assert result.exit_code == 1
    event = _final(result.stdout)
    assert event["event"] == "error"


def test_copy_json_with_prune_and_yes_prune_runs_noninteractively(tmp_path: Path) -> None:
    """The scenario the extension actually relies on: fully non-interactive
    copy + prune, no stdin available at all."""
    src = _make_project(tmp_path)
    dest = tmp_path / "dest"
    runner.invoke(app, ["copy", str(src), str(dest), "--json", "--yes"])

    # exclude app.js too, now everything already copied is stale
    (src / ".copyignore").write_text("node_modules\napp.js\n", encoding="utf-8")

    result = runner.invoke(
        app, ["copy", str(src), str(dest), "--json", "--yes", "--prune", "--yes-prune"], input=""
    )

    assert result.exit_code == 0
    payload = _final(result.stdout)["data"]
    assert payload["prune"]["files_removed"] == 1
    assert not (dest / "app.js").exists()


def test_verify_json_reports_ok(tmp_path: Path) -> None:
    src = _make_project(tmp_path)
    dest = tmp_path / "dest"
    runner.invoke(app, ["copy", str(src), str(dest), "--json", "--yes"])

    result = runner.invoke(app, ["verify", str(src), str(dest), "--json"])

    assert result.exit_code == 0
    payload = _final(result.stdout)["data"]
    assert payload["ok"] is True
    assert payload["checked"] == 1


def test_zip_json_reports_files_written(tmp_path: Path) -> None:
    src = _make_project(tmp_path)
    output = tmp_path / "out.zip"

    result = runner.invoke(app, ["zip", str(src), "--json", "--output", str(output)])

    assert result.exit_code == 0
    payload = _final(result.stdout)["data"]
    assert payload["files_written"] == 1
    assert payload["output"] == output.resolve().as_posix()


def test_stats_json_reports_presets_and_bloat(tmp_path: Path) -> None:
    src = tmp_path / "proj"
    (src / "node_modules").mkdir(parents=True)
    (src / "node_modules" / "pkg.js").write_text("pkg")
    (src / "package.json").write_text("{}", encoding="utf-8")

    result = runner.invoke(app, ["stats", str(src), "--json"])

    assert result.exit_code == 0
    payload = _final(result.stdout)["data"]
    assert payload["preset_names"] == ["node"]
    assert "node_modules" in payload["skipped_dirs"]


def test_init_json_reports_created_file(tmp_path: Path) -> None:
    src = tmp_path / "proj"
    src.mkdir()
    (src / "package.json").write_text("{}", encoding="utf-8")

    result = runner.invoke(app, ["init", str(src), "--json"])

    assert result.exit_code == 0
    payload = _final(result.stdout)["data"]
    assert payload["presets"] == ["node"]
    assert "node_modules" in payload["patterns"]


def test_command_json_skips_clipboard_and_returns_command_text(tmp_path: Path) -> None:
    src = _make_project(tmp_path)
    dest = tmp_path / "dest"

    result = runner.invoke(app, ["command", str(src), str(dest), "--json"])

    assert result.exit_code == 0
    payload = _final(result.stdout)["data"]
    assert "command" in payload
    assert payload["has_negation"] is False
