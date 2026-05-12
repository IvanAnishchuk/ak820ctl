"""Tests for the CLI."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from ak820ctl.cli import app

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    assert "Usage" in result.output


def test_time_help() -> None:
    result = runner.invoke(app, ["time", "--help"])
    assert result.exit_code == 0
    assert "Sync the keyboard clock" in result.output


def test_light_help() -> None:
    result = runner.invoke(app, ["light", "--help"])
    assert result.exit_code == 0
    assert "Lighting mode" in result.output


def test_sleep_help() -> None:
    result = runner.invoke(app, ["sleep", "--help"])
    assert result.exit_code == 0
    assert "sleep" in result.output.lower()


def test_info_no_device() -> None:
    with patch("ak820ctl.cli.find_device", side_effect=RuntimeError("not found")):
        result = runner.invoke(app, ["info"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_light_invalid_mode() -> None:
    result = runner.invoke(app, ["light", "nonexistent"])
    assert result.exit_code == 1
    assert "Unknown mode" in result.output


def test_light_invalid_color() -> None:
    result = runner.invoke(app, ["light", "static", "--color", "xyz"])
    assert result.exit_code == 1
    assert "hex digits" in result.output


def test_sleep_invalid_timeout() -> None:
    result = runner.invoke(app, ["sleep", "999"])
    assert result.exit_code == 1
    assert "Unknown timeout" in result.output


def test_time_invalid_format() -> None:
    result = runner.invoke(app, ["time", "--set", "not-a-time"])
    assert result.exit_code == 1
    assert "Cannot parse" in result.output
