from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class FailedItem:
    path: Path
    error: str
