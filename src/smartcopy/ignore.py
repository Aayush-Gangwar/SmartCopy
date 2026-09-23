from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class IgnoreRules:
    names: set[str]
    case_insensitive: bool

    @classmethod
    def load(cls, copyignore_path: Path) -> "IgnoreRules":
        raw_names: list[str] = []
        # utf-8-sig strips a leading BOM if present (common when the file is
        # saved by Windows editors/PowerShell) and behaves like utf-8
        # otherwise.
        for raw_line in copyignore_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            raw_names.append(line)

        case_insensitive = os.name == "nt"
        if case_insensitive:
            raw_names = [n.casefold() for n in raw_names]
        return cls(names=set(raw_names), case_insensitive=case_insensitive)

    def matches(self, name: str) -> bool:
        candidate = name.casefold() if self.case_insensitive else name
        return candidate in self.names
