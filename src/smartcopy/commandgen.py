from __future__ import annotations

import os
import shlex
from pathlib import Path

from .ignore import IgnoreRules


def _win_quote(value: str) -> str:
    return f'"{value}"' if " " in value or "\t" in value else value


def build_command(src: Path, dest: Path, rules: IgnoreRules) -> tuple[str, bool]:
    """Returns (command_text, had_unsupported_negation)."""
    patterns = [pattern for pattern, negate in rules.rules if not negate]
    has_negation = any(negate for _, negate in rules.rules)

    if os.name == "nt":
        parts = ["robocopy", _win_quote(str(src)), _win_quote(str(dest)), "/E"]
        if patterns:
            parts.append("/XD")
            parts.extend(_win_quote(p) for p in patterns)
            parts.append("/XF")
            parts.extend(_win_quote(p) for p in patterns)
        command = " ".join(parts)
    else:
        parts = ["rsync", "-av"]
        parts.extend(f"--exclude={shlex.quote(p)}" for p in patterns)
        parts.append(shlex.quote(f"{src}/"))
        parts.append(shlex.quote(f"{dest}/"))
        command = " ".join(parts)

    return command, has_negation
