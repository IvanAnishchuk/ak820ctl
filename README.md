# ak820ctl

A short description of the project

## Installation

```bash
uv tool install ak820ctl
# or
pip install ak820ctl
```

## Usage

```bash
ak820ctl --help
```

### Per-Key Custom RGB

Save and restore per-key color configurations as JSON:

```bash
# Save current keyboard colors to a file
ak820ctl perkey --save my_colors.json

# Restore from a saved file
ak820ctl perkey --load my_colors.json

# Use a bundled example scheme
ak820ctl perkey --load examples/perkey/groups.json

# Set all keys to one color
ak820ctl perkey --all ff0000

# Set individual keys by LED index
ak820ctl perkey --key 42:ff0000 --key 56:00ff00

# Show current per-key state
ak820ctl perkey

# Dump live state as JSON to stdout
ak820ctl perkey --dump
```

Bundled examples in `examples/perkey/`:
- **groups** — semantic color grouping by key function (letters, numbers, F-keys, etc.)
- **rainbow** — full spectrum across all keys
- **blocks** — row-band color pattern
- **ocean** — cool blues and teals
- **sunset** — warm reds and oranges
- **stealth** — dim amber for dark environments

See `src/ak820ctl/keymap.json` for the full LED index → physical key mapping
(81 keys mapped out of 144 LED positions).

## Development

```bash
git clone https://github.com/IvanAnishchuk/ak820ctl.git
cd ak820ctl
uv sync

# Run tests
uv run pytest

# Run lints
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run ty check

# Run full pre-commit suite
uv run pre-commit run --all-files

# Run supply-chain audit
uv run python scripts/audit.py
```

## License

CC0-1.0
