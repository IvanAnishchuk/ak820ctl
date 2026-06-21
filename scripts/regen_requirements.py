"""Export requirements from uv.lock -- the single export definition.

uv.lock is the source of truth; requirements*.txt are generated on demand and
never committed. Two modes:

    # stream ONE set to stdout (the `regen | ...` pipe; default prod-only)
    uv run python scripts/regen_requirements.py --stdout [--include-dev]

    # write BOTH files into a directory (meson build dir / release artifact)
    uv run python scripts/regen_requirements.py --output-dir DIR

No args: writes both files into .reports/requirements/ (git-ignored).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from rich.console import Console

# All human-facing output goes to stderr so stdout stays a clean requirements
# stream in --stdout (pipe) mode.
console = Console(stderr=True)
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / ".reports" / "requirements"


def export(*, include_dev: bool) -> str:
    """Return uv-exported requirements text for one dependency set."""
    cmd = ["uv", "export", "--format", "requirements-txt", "--no-emit-project"]
    if not include_dev:
        cmd.append("--no-dev")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, check=False)
    if result.returncode != 0:
        console.print(f"[bold red]Error:[/] {result.stderr}", highlight=False)
        sys.exit(result.returncode)
    return result.stdout


def write_files(output_dir: Path) -> None:
    """Write both prod and prod+dev requirements files into output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "requirements.txt").write_text(export(include_dev=False), encoding="utf-8")
    (output_dir / "requirements-dev.txt").write_text(export(include_dev=True), encoding="utf-8")
    console.print(f"  wrote requirements.txt, requirements-dev.txt to {output_dir}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Export requirements from uv.lock.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--stdout", action="store_true", help="write one set to stdout (pipe)")
    mode.add_argument("--output-dir", type=Path, help="write both files into this directory")
    parser.add_argument(
        "--include-dev", action="store_true", help="(stdout mode) include dev dependencies"
    )
    args = parser.parse_args(argv)
    if args.include_dev and not args.stdout:
        parser.error("--include-dev only applies in --stdout mode")

    if args.stdout:
        sys.stdout.write(export(include_dev=args.include_dev))
    else:
        write_files(args.output_dir or DEFAULT_OUTPUT_DIR)


if __name__ == "__main__":
    main()
