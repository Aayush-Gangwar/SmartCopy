# SmartCopy

### CTRL+A for developers. Copy only source code, never dependencies.

Every developer has done this: `Ctrl+A`, `Ctrl+C` on a project folder to back it up or share it, only to end up copying 8 GB of `node_modules` along with the 200 MB of code that actually matters. SmartCopy fixes that at the root — it understands your project the way `.gitignore` does, and applies that understanding to copying, not just version control.

```bash
$ smartcopy preview .
Will Copy
  src/
  package.json
  vite.config.js

Will Skip
  node_modules
  dist

41 files (13.1 MB) will be copied  -  2 skipped (59.4 MB saved, 82.0%)
```

---

## Why this exists

| Tool | Discoverable | Preview before acting | Zero-config |
|---|---|---|---|
| **SmartCopy** | ✅ | ✅ | ✅ (`.gitignore` fallback) |
| `robocopy /XD` | ❌ needs memorized flags | ❌ | ❌ |
| `rsync --exclude` | ❌ CLI-only, easy to typo | ❌ | ❌ |
| `.gitignore` alone | ✅ | ❌ | ✅ |
| Ad-hoc scripts / manual dedup | ❌ | ❌ | ❌ |

---

## Install

Not yet published to PyPI. Install from source:

```bash
git clone <this-repo>
cd SmartCopy
pip install -e .
```

Requires Python ≥ 3.9. Pulls in `typer`, `rich`, and `pyperclip`.

---

## Quick start

```bash
# See what would happen - nothing is touched
smartcopy preview .

# No .copyignore yet? Generate one - auto-detects your project type
smartcopy init                      # writes .copyignore from detected presets
smartcopy init --preset python      # or force a specific one

# Copy source only, skipping everything in .copyignore
smartcopy copy D:\Backup

# No .copyignore, no setup - just tell me how much bloat is in this project
smartcopy stats .
```

`SRC` is optional wherever it appears (`copy`) — it defaults to the current directory, so `smartcopy copy D:\Backup` from inside your project works exactly like `smartcopy copy . D:\Backup`.

---

## Commands

| Command | What it does |
|---|---|
| `smartcopy preview [PATH]` | Shows what would be copied vs. skipped, and the bytes saved. Changes nothing. |
| `smartcopy copy [SRC] DEST` | Copies everything not excluded (merges into an existing destination, never deletes). |
| `smartcopy stats [PATH]` | Zero-config bloat report — no `.copyignore` required. Auto-detects your stack and tells you how much of the project is disposable. |
| `smartcopy init [PATH]` | Writes a `.copyignore` from an auto-detected or explicitly chosen preset (`node`, `python`, `java`, `dotnet`, `rust`, `general`). |

---

## `.copyignore`

```text
# Comments and blank lines are ignored
node_modules/
dist/
*.log

# Negation - re-includes something an earlier rule excluded
!important.log

# Wildcards work like .gitignore
.env.*.local
```

- **Full gitignore-style matching**: wildcards (`*`, `?`, `[...]`), `!negation` with last-rule-wins semantics, comments, trailing slashes on directories — all supported.
- **No `.copyignore` yet?** SmartCopy automatically falls back to your existing `.gitignore`, so most projects work with zero setup.
- **Case rules match the OS**: case-insensitive on Windows, case-sensitive on macOS/Linux — not just "however the pattern happened to be typed."

---

## What's next

`copy --incremental`/`--prune`, `verify`, `zip`, and generating a native `robocopy`/`rsync` command are next on the roadmap, along with a VS Code extension.
