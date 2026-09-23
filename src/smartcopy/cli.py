from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

import pyperclip
import typer

from .commandgen import build_command
from .copier import execute
from .ignore import IgnoreRules
from .jsonio import (
    copy_stats_to_dict,
    preview_to_dict,
    prune_stats_to_dict,
    scan_result_to_dict,
    verify_result_to_dict,
    zip_stats_to_dict,
)
from .presets import PRESETS, default_patterns, detect_presets
from .pruner import find_prune_files
from .pruner import prune as run_prune
from .report import (
    console,
    render_copy_summary,
    render_file_diff,
    render_preview,
    render_prune_preview,
    render_prune_summary,
    render_stats,
    render_verify,
    render_zip_summary,
)
from .scanner import scan, top_level
from .verifier import diff_text
from .verifier import verify as run_verify
from .zipper import create_zip

app = typer.Typer(help="CTRL+A for developers - copy source, skip dependencies.")


def _error(json_mode: bool, message: str) -> None:
    if json_mode:
        print(json.dumps({"event": "error", "message": message}), flush=True)
    else:
        console.print(f"[red]{message}[/red]")
    raise typer.Exit(code=1)


def _emit_result(json_mode: bool, payload: dict) -> None:
    if json_mode:
        print(json.dumps({"event": "result", "data": payload}), flush=True)


def _json_progress(label: str) -> Callable[[int, int], None]:
    def _report(completed: int, total: int) -> None:
        print(json.dumps({"event": "progress", "label": label, "completed": completed, "total": total}), flush=True)

    return _report


def _resolve_src_dest(paths: list[Path], json_mode: bool = False) -> tuple[Path, Path]:
    if len(paths) == 1:
        return Path("."), paths[0]
    if len(paths) == 2:
        return paths[0], paths[1]
    _error(json_mode, "Usage: [SRC] DEST")


def _require_existing_dir(path: Path, json_mode: bool = False) -> None:
    if not path.is_dir():
        _error(json_mode, f"{path} is not a directory (or doesn't exist).")


def _guard_dest_not_inside_src(root: Path, dest_root: Path, json_mode: bool = False) -> None:
    if dest_root == root or root in dest_root.parents:
        _error(
            json_mode,
            f"Destination {dest_root} is the same as, or inside, the source {root}. "
            f"Choose a destination outside the source tree.",
        )


def _load_rules(root: Path, ignore_file: Optional[Path], json_mode: bool = False) -> IgnoreRules:
    if ignore_file:
        if not ignore_file.is_file():
            _error(json_mode, f"No ignore file found at {ignore_file}.")
        return IgnoreRules.load(ignore_file)

    copyignore = root / ".copyignore"
    if copyignore.is_file():
        return IgnoreRules.load(copyignore)

    gitignore = root / ".gitignore"
    if gitignore.is_file():
        if not json_mode:
            console.print(f"[yellow]No .copyignore found - using {gitignore} instead.[/yellow]")
        return IgnoreRules.load(gitignore)

    _error(
        json_mode,
        f"No .copyignore or .gitignore found in {root}. "
        f"Use --ignore-file, or run 'smartcopy init' to create one.",
    )


@app.command()
def preview(
    path: Path = typer.Argument(Path("."), help="Project root to scan."),
    ignore_file: Optional[Path] = typer.Option(None, "--ignore-file", help="Path to a .copyignore file."),
    verbose: bool = typer.Option(False, "--verbose", help="List every file that will be copied."),
    compare_dest: Optional[Path] = typer.Option(
        None,
        "--compare-dest",
        help="Also report which files there would be removed by 'copy --prune' - read-only, nothing is deleted.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON instead of formatted text."),
) -> None:
    root = path.resolve()
    _require_existing_dir(root, json_output)
    rules = _load_rules(root, ignore_file, json_output)
    result = scan(root, rules)
    top_copy, top_skip = top_level(root, rules)

    would_prune = None
    if compare_dest is not None:
        would_prune = find_prune_files(result, compare_dest.resolve())

    if json_output:
        payload = preview_to_dict(result, top_copy, top_skip, verbose)
        if would_prune is not None:
            payload["would_prune"] = [p.as_posix() for p in would_prune]
        _emit_result(json_output, payload)
    else:
        render_preview(result, top_copy, top_skip, verbose)
        if would_prune is not None:
            if would_prune:
                render_prune_preview(would_prune)
            else:
                console.print("[green]Nothing would be pruned - destination already matches.[/green]")


@app.command()
def copy(
    paths: list[Path] = typer.Argument(
        ..., help="[SRC] DEST - SRC defaults to the current directory when omitted."
    ),
    ignore_file: Optional[Path] = typer.Option(None, "--ignore-file", help="Path to a .copyignore file."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
    incremental: bool = typer.Option(
        False, "--incremental", help="Skip files unchanged since last copy (by size + mtime)."
    ),
    prune: bool = typer.Option(
        False,
        "--prune",
        help="After copying, remove anything in DEST not in the current source - true mirror, like robocopy /MIR.",
    ),
    yes_prune: bool = typer.Option(
        False, "--yes-prune", help="Skip prune's own separate confirmation too (only meaningful with --prune)."
    ),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON instead of formatted text."),
) -> None:
    src, dest = _resolve_src_dest(paths, json_output)
    root = src.resolve()
    dest_root = dest.resolve()
    _require_existing_dir(root, json_output)
    _guard_dest_not_inside_src(root, dest_root, json_output)

    if json_output and not yes:
        _error(json_output, "--json requires --yes (no interactive confirmation is possible).")
    if json_output and prune and not yes_prune:
        _error(json_output, "--json with --prune requires --yes-prune (no interactive confirmation is possible).")

    rules = _load_rules(root, ignore_file, json_output)
    result = scan(root, rules)

    if not yes:
        typer.confirm(
            f"Copy {len(result.included_files)} files from {root} to {dest_root}?",
            abort=True,
        )

    copy_stats = execute(
        result,
        dest_root,
        show_progress=not json_output,
        incremental=incremental,
        on_progress=_json_progress("Copying") if json_output else None,
    )
    if not json_output:
        render_copy_summary(copy_stats)
    had_failures = bool(copy_stats.failed)

    prune_payload = None
    if prune:
        prune_targets = find_prune_files(result, dest_root)
        if not prune_targets:
            if not json_output:
                console.print("[green]Nothing to prune - destination already matches.[/green]")
        else:
            if not json_output:
                render_prune_preview(prune_targets)
            if not yes_prune:
                typer.confirm(
                    f"Delete these {len(prune_targets)} file(s) from {dest_root}? This cannot be undone.",
                    abort=True,
                )
            prune_stats = run_prune(
                result,
                dest_root,
                show_progress=not json_output,
                on_progress=_json_progress("Pruning") if json_output else None,
            )
            had_failures = had_failures or bool(prune_stats.failed)
            prune_payload = prune_stats_to_dict(prune_stats)
            if not json_output:
                render_prune_summary(prune_stats)

    payload = copy_stats_to_dict(copy_stats)
    payload["prune"] = prune_payload
    _emit_result(json_output, payload)

    if had_failures:
        raise typer.Exit(code=1)


@app.command(name="command")
def command_cmd(
    paths: list[Path] = typer.Argument(
        ..., help="[SRC] DEST - SRC defaults to the current directory when omitted."
    ),
    ignore_file: Optional[Path] = typer.Option(None, "--ignore-file", help="Path to a .copyignore file."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON instead of formatted text."),
) -> None:
    """Generate a robocopy/rsync command (and copy it to the clipboard) instead of copying now."""
    src, dest = _resolve_src_dest(paths, json_output)
    root = src.resolve()
    _require_existing_dir(root, json_output)
    rules = _load_rules(root, ignore_file, json_output)

    command_text, has_negation = build_command(root, dest.resolve(), rules)

    if json_output:
        _emit_result(json_output, {"command": command_text, "has_negation": has_negation})
        return

    console.print(command_text)
    try:
        pyperclip.copy(command_text)
        console.print("[green]Copied to clipboard.[/green]")
    except Exception:
        console.print("[yellow]Could not access the clipboard - copy the command above manually.[/yellow]")

    if has_negation:
        console.print(
            "[yellow]Warning: '!negation' rules in your ignore file can't be expressed in this "
            "command and were omitted. Use 'smartcopy copy' directly if you rely on them.[/yellow]"
        )


@app.command()
def verify(
    paths: list[Path] = typer.Argument(
        ..., help="[SRC] DEST - SRC defaults to the current directory when omitted."
    ),
    ignore_file: Optional[Path] = typer.Option(None, "--ignore-file", help="Path to a .copyignore file."),
    diff: bool = typer.Option(False, "--diff", help="Show a diff for every mismatched file."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON instead of formatted text."),
) -> None:
    """Confirm a copy is intact by comparing size and sha256 hash for every file."""
    src, dest = _resolve_src_dest(paths, json_output)
    root = src.resolve()
    dest_root = dest.resolve()
    _require_existing_dir(root, json_output)
    rules = _load_rules(root, ignore_file, json_output)
    result = scan(root, rules)

    verify_result = run_verify(
        result,
        dest_root,
        show_progress=not json_output,
        on_progress=_json_progress("Verifying") if json_output else None,
    )

    if json_output:
        _emit_result(json_output, verify_result_to_dict(verify_result))
    else:
        render_verify(verify_result)
        if diff:
            for rel in verify_result.size_mismatch + verify_result.hash_mismatch:
                render_file_diff(rel, diff_text(root / rel, dest_root / rel))

    if not verify_result.ok:
        raise typer.Exit(code=1)


@app.command(name="zip")
def zip_cmd(
    path: Path = typer.Argument(Path("."), help="Project root to zip."),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output .zip path (default: <project-name>-clean.zip next to the project)."
    ),
    ignore_file: Optional[Path] = typer.Option(None, "--ignore-file", help="Path to a .copyignore file."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON instead of formatted text."),
) -> None:
    root = path.resolve()
    _require_existing_dir(root, json_output)
    rules = _load_rules(root, ignore_file, json_output)
    result = scan(root, rules)

    out = (output or root.parent / f"{root.name}-clean.zip").resolve()
    zip_stats = create_zip(
        result,
        out,
        show_progress=not json_output,
        on_progress=_json_progress("Zipping") if json_output else None,
    )

    if json_output:
        _emit_result(json_output, zip_stats_to_dict(zip_stats, out))
    else:
        render_zip_summary(zip_stats, out)

    if zip_stats.failed:
        raise typer.Exit(code=1)


@app.command()
def stats(
    path: Path = typer.Argument(Path("."), help="Project root to analyze."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON instead of formatted text."),
) -> None:
    """Zero-config bloat report - no .copyignore required."""
    root = path.resolve()
    _require_existing_dir(root, json_output)
    preset_names = detect_presets(root)
    rules = IgnoreRules.from_patterns(default_patterns(root))
    result = scan(root, rules)

    if json_output:
        payload = scan_result_to_dict(result)
        payload["preset_names"] = preset_names
        _emit_result(json_output, payload)
    else:
        render_stats(result, preset_names)


@app.command()
def init(
    path: Path = typer.Argument(Path("."), help="Project root to create a .copyignore in."),
    preset: Optional[str] = typer.Option(
        None, "--preset", help=f"One of: {', '.join(PRESETS)}. Auto-detected from the project if omitted."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing .copyignore."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON instead of formatted text."),
) -> None:
    root = path.resolve()
    _require_existing_dir(root, json_output)
    target = root / ".copyignore"
    if target.exists() and not force:
        _error(json_output, f"{target} already exists. Use --force to overwrite.")

    if preset:
        if preset not in PRESETS:
            _error(json_output, f"Unknown preset '{preset}'. Choose from: {', '.join(PRESETS)}")
        keys = [preset]
    else:
        keys = detect_presets(root)

    patterns: list[str] = []
    for key in keys:
        patterns.extend(PRESETS[key])
    patterns = list(dict.fromkeys(patterns))

    target.write_text("\n".join(patterns) + "\n", encoding="utf-8")

    if json_output:
        _emit_result(json_output, {"target": target.as_posix(), "presets": keys, "patterns": patterns})
    else:
        console.print(f"[green]Created {target}[/green] using preset(s): {', '.join(keys)}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
