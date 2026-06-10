"""Smoke test for the `python -m ak820ctl` entry point."""

from __future__ import annotations

import subprocess
import sys

from ak820ctl import __version__


def test_module_main_runs_and_prints_help() -> None:
    """`python -m ak820ctl` with no args should print the typer help banner."""
    result = subprocess.run(
        [sys.executable, "-m", "ak820ctl"],
        check=False,
        capture_output=True,
        text=True,
    )
    # typer prints help to stdout and exits 0 when `no_args_is_help=True`,
    # but some versions exit non-zero — accept either as long as the help
    # banner reached the user.
    assert "Usage" in (result.stdout + result.stderr)


def test_module_main_version_flag() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ak820ctl", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert __version__ in result.stdout
