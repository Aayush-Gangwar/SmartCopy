"""Build a standalone smartcopy executable for the current OS via PyInstaller.

Produces a single-file binary with no Python dependency for the end user.
Must be run separately on each target OS (Windows/macOS/Linux) - PyInstaller
does not cross-compile.

Usage: python build.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def main() -> None:
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--onefile",
            "--name",
            "smartcopy",
            "--distpath",
            str(ROOT / "dist"),
            "--workpath",
            str(ROOT / "build" / "pyinstaller"),
            "--specpath",
            str(ROOT / "build" / "pyinstaller"),
            "--paths",
            str(ROOT / "src"),
            "--clean",
            str(ROOT / "entry_point.py"),
        ]
    )


if __name__ == "__main__":
    main()
