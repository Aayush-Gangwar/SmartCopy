from pathlib import Path

from smartcopy.ignore import IgnoreRules


def test_parses_literal_names_skipping_blanks_and_comments(tmp_path: Path) -> None:
    copyignore = tmp_path / ".copyignore"
    copyignore.write_text("node_modules\n\n# comment\nvenv\n", encoding="utf-8")

    rules = IgnoreRules.load(copyignore)

    assert rules.matches("node_modules")
    assert rules.matches("venv")
    assert not rules.matches("src")
    assert not rules.matches("# comment")


def test_handles_utf8_bom(tmp_path: Path) -> None:
    copyignore = tmp_path / ".copyignore"
    copyignore.write_bytes("node_modules\ndist\n".encode("utf-8-sig"))

    rules = IgnoreRules.load(copyignore)

    assert rules.matches("node_modules")
    assert rules.matches("dist")


def test_strips_gitignore_style_trailing_slash(tmp_path: Path) -> None:
    copyignore = tmp_path / ".copyignore"
    copyignore.write_text("node_modules/\ndist/\n", encoding="utf-8")

    rules = IgnoreRules.load(copyignore)

    assert rules.matches("node_modules")
    assert rules.matches("dist")


def test_wildcard_patterns_match_like_gitignore(tmp_path: Path) -> None:
    copyignore = tmp_path / ".copyignore"
    copyignore.write_text("*.local\nnpm-debug.log*\n*.suo\n", encoding="utf-8")

    rules = IgnoreRules.load(copyignore)

    assert rules.matches("foo.local")
    assert rules.matches("npm-debug.log.1234")
    assert rules.matches("project.suo")
    assert not rules.matches("app.js")


def test_negation_reincludes_a_later_match(tmp_path: Path) -> None:
    copyignore = tmp_path / ".copyignore"
    copyignore.write_text("*.log\n!important.log\n", encoding="utf-8")

    rules = IgnoreRules.load(copyignore)

    assert rules.matches("debug.log")
    assert not rules.matches("important.log")


def test_last_matching_rule_wins(tmp_path: Path) -> None:
    copyignore = tmp_path / ".copyignore"
    copyignore.write_text("!keep.txt\nkeep.txt\n", encoding="utf-8")

    rules = IgnoreRules.load(copyignore)

    assert rules.matches("keep.txt")


def test_case_insensitive_on_windows(tmp_path: Path) -> None:
    copyignore = tmp_path / ".copyignore"
    copyignore.write_text("Node_Modules\n", encoding="utf-8")

    # Explicit override rather than monkeypatching os.name - patching that
    # globally leaks into pathlib and pytest's own internals process-wide,
    # since `import os` everywhere binds the same module object.
    rules = IgnoreRules.load(copyignore, case_insensitive=True)

    assert rules.matches("node_modules")
    assert rules.matches("NODE_MODULES")


def test_case_sensitive_off_windows(tmp_path: Path) -> None:
    copyignore = tmp_path / ".copyignore"
    copyignore.write_text("node_modules\n", encoding="utf-8")

    rules = IgnoreRules.load(copyignore, case_insensitive=False)

    assert rules.matches("node_modules")
    assert not rules.matches("NODE_MODULES")


def test_slash_patterns_are_anchored_to_the_given_path(tmp_path: Path) -> None:
    copyignore = tmp_path / ".copyignore"
    copyignore.write_text("extension/node_modules/\n", encoding="utf-8")

    rules = IgnoreRules.load(copyignore)

    # Anchored: matches only at that exact relative path...
    assert rules.matches("node_modules", "extension/node_modules")
    # ...not a same-named directory elsewhere in the tree.
    assert not rules.matches("node_modules", "packages/a/node_modules")
    assert not rules.matches("node_modules", "node_modules")


def test_slashless_pattern_still_matches_by_name_anywhere(tmp_path: Path) -> None:
    copyignore = tmp_path / ".copyignore"
    copyignore.write_text("node_modules\n", encoding="utf-8")

    rules = IgnoreRules.load(copyignore)

    assert rules.matches("node_modules", "node_modules")
    assert rules.matches("node_modules", "packages/a/node_modules")
