from pathlib import Path

from smartcopy.commandgen import build_command
from smartcopy.ignore import IgnoreRules


def test_windows_generates_robocopy(monkeypatch) -> None:
    monkeypatch.setattr("smartcopy.commandgen.os.name", "nt")
    rules = IgnoreRules.from_patterns(["node_modules", "*.log"], case_insensitive=True)

    command, has_negation = build_command(Path("C:/src"), Path("D:/backup"), rules)

    assert command.startswith("robocopy")
    assert "/E" in command
    assert "/XD" in command
    assert "/XF" in command
    assert "node_modules" in command
    assert "*.log" in command
    assert has_negation is False


def test_posix_generates_rsync(monkeypatch) -> None:
    monkeypatch.setattr("smartcopy.commandgen.os.name", "posix")
    rules = IgnoreRules.from_patterns(["node_modules"], case_insensitive=False)

    command, has_negation = build_command(Path("/src"), Path("/backup"), rules)

    assert command.startswith("rsync")
    assert "--exclude=node_modules" in command
    assert has_negation is False


def test_negation_is_dropped_and_flagged(monkeypatch) -> None:
    monkeypatch.setattr("smartcopy.commandgen.os.name", "posix")
    rules = IgnoreRules(rules=[("*.log", False), ("important.log", True)], case_insensitive=False)

    command, has_negation = build_command(Path("/src"), Path("/backup"), rules)

    assert has_negation is True
    assert "important.log" not in command
    # shlex.quote wraps the glob in quotes so the shell doesn't expand it
    # before rsync sees it - that's correct, not a bug.
    assert "--exclude=" in command and "*.log" in command
