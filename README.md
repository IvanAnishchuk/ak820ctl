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
