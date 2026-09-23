from __future__ import annotations

from pathlib import Path

GENERAL: list[str] = [
    ".git",
    ".svn",
    ".hg",
    ".DS_Store",
    "Thumbs.db",
    ".vscode",
    ".idea",
    "*.suo",
    "*.ntvs*",
    "*.njsproj",
    "*.sln",
    "*.swp",
    "__pycache__",
    "*.pyc",
]

NODE: list[str] = GENERAL + [
    "node_modules",
    ".pnpm-store",
    "dist",
    "dist-ssr",
    "build",
    ".next",
    ".nuxt",
    ".cache",
    "coverage",
    ".env",
    ".env.local",
    ".env.*.local",
    "npm-debug.log*",
    "yarn-debug.log*",
    "yarn-error.log*",
    "pnpm-debug.log*",
]

PYTHON: list[str] = GENERAL + [
    "venv",
    ".venv",
    "env",
    "*.egg-info",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    "build",
    "dist",
]

JAVA: list[str] = GENERAL + [
    "target",
    ".gradle",
    "build",
    "out",
]

DOTNET: list[str] = GENERAL + [
    "bin",
    "obj",
    "packages",
    "*.user",
]

RUST: list[str] = GENERAL + [
    "target",
]

PRESETS: dict[str, list[str]] = {
    "general": GENERAL,
    "node": NODE,
    "python": PYTHON,
    "java": JAVA,
    "dotnet": DOTNET,
    "rust": RUST,
}


def detect_presets(root: Path) -> list[str]:
    detected: list[str] = []
    if (root / "package.json").exists():
        detected.append("node")
    if any((root / name).exists() for name in ("requirements.txt", "pyproject.toml", "setup.py")):
        detected.append("python")
    if (root / "pom.xml").exists() or any(root.glob("build.gradle*")):
        detected.append("java")
    if any(root.glob("*.csproj")) or any(root.glob("*.sln")):
        detected.append("dotnet")
    if (root / "Cargo.toml").exists():
        detected.append("rust")
    return detected or ["general"]


def default_patterns(root: Path) -> list[str]:
    """Zero-config pattern set for `smartcopy stats` - merges every preset
    detected from the project's marker files, deduplicated in order."""
    merged: list[str] = []
    for key in detect_presets(root):
        merged.extend(PRESETS[key])
    return list(dict.fromkeys(merged))
