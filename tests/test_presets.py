from pathlib import Path

from smartcopy.presets import default_patterns, detect_presets


def test_detects_node_project(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")

    assert detect_presets(tmp_path) == ["node"]


def test_detects_python_project(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")

    assert detect_presets(tmp_path) == ["python"]


def test_falls_back_to_general_when_nothing_detected(tmp_path: Path) -> None:
    assert detect_presets(tmp_path) == ["general"]


def test_default_patterns_merge_without_duplicates(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")

    patterns = default_patterns(tmp_path)

    assert "node_modules" in patterns
    assert "venv" in patterns
    assert len(patterns) == len(set(patterns))
