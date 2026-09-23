from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class IgnoreRules:
    rules: list[str]
    case_insensitive: bool

    @classmethod
    def load(cls, copyignore_path: Path) -> "IgnoreRules":
        raw_rules: list[str] = []
        # utf-8-sig strips a leading BOM if present (common when the file is
        # saved by Windows editors/PowerShell) and behaves like utf-8
        # otherwise.
        for raw_line in copyignore_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            # gitignore-style trailing slash ("node_modules/") marks a
            # directory-only rule; we match by bare name regardless of
            # file/dir, so the slash itself carries no extra information.
            line = line.rstrip("/\\")
            if not line:
                continue
            raw_rules.append(line)

        case_insensitive = os.name == "nt"
        if case_insensitive:
            raw_rules = [p.casefold() for p in raw_rules]
        return cls(rules=raw_rules, case_insensitive=case_insensitive)

    def matches(self, name: str) -> bool:
        candidate = name.casefold() if self.case_insensitive else name
        # fnmatchcase (not fnmatch) so casing is controlled entirely by the
        # casefold above, independent of the host OS's own case rules.
        return any(fnmatch.fnmatchcase(candidate, pattern) for pattern in self.rules)
