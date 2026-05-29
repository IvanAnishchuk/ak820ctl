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

## Conventions

- Python 3.14+, src layout, hatchling build backend
- Ruff for linting (line-length 100, security rules enabled) and formatting
- ty for type checking
- pytest with coverage (threshold in pyproject.toml)
- Conventional commits enforced by pre-commit hook
- All CI checks must pass before merge (see .github/workflows/ci.yml)
- Never squash merge PRs — use merge commits to preserve commit history
- Never use `git add -A` or `git add .` — always stage individual files by name
