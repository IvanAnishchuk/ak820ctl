# CLAUDE.md

## Project Overview

ak820ctl -- Linux CLI tool for controlling Ajazz AK820 keyboard (time, LED, sleep)

CLI tool built with typer + rich + hidapi. Source layout under `src/ak820ctl/`.
Communicates via USB HID feature reports on Interface 3 (Usage Page 0xFF13).
Protocol reverse-engineered from Wireshark captures of the Windows driver.

## Commands

```bash
# Install dependencies
uv sync

# Run the CLI
uv run ak820ctl --help

# Run tests with coverage
uv run pytest

# Lint + format
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/

# Type check
uv run ty check

# Full pre-commit suite
uv run pre-commit run --all-files

# Supply-chain audit (pip-audit + SBOM)
uv run python scripts/audit.py
```

## CLI subcommands

Top-level: `time`, `light`, `sleep`, `info`, `dump`, `perkey`, `image`, `gif`, `restore`.

### `perkey` — per-key RGB (144 keys)

- `--dump` / `-d` — print live per-key state as JSON to stdout (requires connected keyboard).
- `--dump-stored` — print stored-in-flash state as JSON.
- `--save PATH` / `-s` — save live state to a JSON file.
- `--load PATH` / `-l` — load colors from a JSON file and write them.
- `--all RRGGBB` / `-a` — set every key to one color.
- `--key INDEX:RRGGBB` / `-k` — set one key by index (repeatable).
- `--brightness 0-5` / `-b` — brightness for write ops (default 5).
- No args: shows live state in a TTY view.

JSON format: list of `{"index": int, "r": int, "g": int, "b": int}` for indices 0-143.

### Key index → name mapping

`src/ak820ctl/data/keymap.json` maps stringified indices (`"0"`..`"143"`) to key names like
`"esc"`, `"caps"`, `"lshift"`, `"win"`, `"fn"`. Some indices are `null` (unused slots)
— always include them when listing "all keys with color X", don't silently drop them.

## Conventions

- Python 3.14+, src layout, hatchling build backend
- Ruff for linting (line-length 100, security rules enabled) and formatting
- ty for type checking
- pytest with coverage (threshold in pyproject.toml)
- Conventional commits enforced by pre-commit hook
- All CI checks must pass before merge (see .github/workflows/ci.yml)
- Never squash merge PRs — use merge commits to preserve commit history
- Never use `git add -A` or `git add .` — always stage individual files by name
