from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass
class IgnoreRules:
    # (pattern, negate) in file order - gitignore semantics: the last rule
    # that matches a given name wins, so a later "!pattern" can re-include
    # something an earlier rule excluded.
    rules: list[tuple[str, bool]]
    case_insensitive: bool

    @classmethod
    def load(cls, copyignore_path: Path, case_insensitive: Optional[bool] = None) -> "IgnoreRules":
        raw_rules: list[tuple[str, bool]] = []
        # utf-8-sig strips a leading BOM if present (common when the file is
        # saved by Windows editors/PowerShell) and behaves like utf-8 otherwise.
        for raw_line in copyignore_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            negate = line.startswith("!")
            if negate:
                line = line[1:].strip()
            # gitignore-style trailing slash ("node_modules/") marks a
            # directory-only rule; we match by bare name regardless of
            # file/dir, so the slash itself carries no extra information.
            line = line.rstrip("/\\")
            if not line:
                continue
            raw_rules.append((line, negate))

        # Explicit override lets callers (and tests) exercise both branches
        # without monkeypatching the global os.name - patching that leaks
        # into pathlib and pytest's own internals process-wide, since
        # `import os` everywhere binds the same module object.
        ci = (os.name == "nt") if case_insensitive is None else case_insensitive
        if ci:
            raw_rules = [(pattern.casefold(), negate) for pattern, negate in raw_rules]
        return cls(rules=raw_rules, case_insensitive=ci)

    @classmethod
    def from_patterns(cls, patterns: Iterable[str], case_insensitive: Optional[bool] = None) -> "IgnoreRules":
        """Build rules from a plain pattern list - no file, no negation.
        Used for built-in default/preset pattern sets."""
        ci = (os.name == "nt") if case_insensitive is None else case_insensitive
        normalized = [p.casefold() if ci else p for p in patterns]
        return cls(rules=[(p, False) for p in normalized], case_insensitive=ci)

    def matches(self, name: str, rel_posix: Optional[str] = None) -> bool:
        """rel_posix is the entry's path relative to the scan root
        (posix-style). A pattern containing "/" is anchored - matched
        against that full relative path, the same way a slash in a real
        .gitignore line anchors it to a specific location instead of
        matching the name anywhere in the tree. A pattern with no "/"
        matches the bare name at any depth. Defaults rel_posix to name
        for callers (and tests) that only care about basename matching."""
        if rel_posix is None:
            rel_posix = name
        name_candidate = name.casefold() if self.case_insensitive else name
        path_candidate = rel_posix.casefold() if self.case_insensitive else rel_posix
        result = False
        for pattern, negate in self.rules:
            candidate = path_candidate if "/" in pattern else name_candidate
            if fnmatch.fnmatchcase(candidate, pattern):
                result = not negate
        return result
