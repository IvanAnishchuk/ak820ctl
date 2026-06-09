"""Tests for the CLI."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from ak820ctl.cli import app

runner = CliRunner()

REPO_ROOT = Path(__file__).resolve().parent.parent
THEMES_DIR = REPO_ROOT / "src" / "ak820ctl" / "data" / "themes"
LAYOUTS_DIR = REPO_ROOT / "src" / "ak820ctl" / "data" / "layouts"
COMPILED_DIR = REPO_ROOT / "examples" / "perkey"


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


# ---------------------------- theme-compile ----------------------------


def test_theme_compile_to_stdout_matches_compiled_file() -> None:
    """No --output: prints the compiled JSON to stdout, byte-identical."""
    src = THEMES_DIR / "groups-solarized-theme.json"
    expected = (COMPILED_DIR / "groups-solarized.json").read_text(encoding="utf-8")
    result = runner.invoke(app, ["theme-compile", str(src)])
    assert result.exit_code == 0
    assert result.output == expected


def test_theme_compile_to_output_file(tmp_path: Path) -> None:
    src = THEMES_DIR / "groups-solarized-theme.json"
    out = tmp_path / "out.json"
    result = runner.invoke(app, ["theme-compile", str(src), "--output", str(out)])
    assert result.exit_code == 0
    assert "Compiled theme written to" in result.output
    expected = (COMPILED_DIR / "groups-solarized.json").read_text(encoding="utf-8")
    assert out.read_text(encoding="utf-8") == expected


def test_theme_compile_with_explicit_layout(tmp_path: Path) -> None:
    """Pastel themes need --layout perrow.json."""
    src = THEMES_DIR / "rows-pastel-turquoise-theme.json"
    layout = LAYOUTS_DIR / "perrow.json"
    out = tmp_path / "out.json"
    result = runner.invoke(
        app,
        ["theme-compile", str(src), "--layout", str(layout), "-o", str(out)],
    )
    assert result.exit_code == 0
    expected = (COMPILED_DIR / "rows-pastel-turquoise.json").read_text(encoding="utf-8")
    assert out.read_text(encoding="utf-8") == expected


def test_theme_compile_missing_source() -> None:
    result = runner.invoke(app, ["theme-compile", "/nonexistent/path.json"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_theme_compile_unknown_group(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus.json"
    bogus.write_text(
        json.dumps({"base": "#000000", "groups": {"not_a_real_group": "#ff0000"}}),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["theme-compile", str(bogus)])
    assert result.exit_code == 1
    assert "not_a_real_group" in result.output


def test_theme_compile_unknown_override(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus.json"
    bogus.write_text(
        json.dumps({"base": "#000000", "overrides": {"not_a_key": "#ff0000"}}),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["theme-compile", str(bogus)])
    assert result.exit_code == 1
    assert "not_a_key" in result.output


def test_theme_compile_hex_without_hash_rejected(tmp_path: Path) -> None:
    """HexColor validation requires a leading '#'."""
    bogus = tmp_path / "bogus.json"
    bogus.write_text(json.dumps({"base": "ff0000"}), encoding="utf-8")
    result = runner.invoke(app, ["theme-compile", str(bogus)])
    assert result.exit_code == 1


def test_theme_compile_malformed_hex(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus.json"
    bogus.write_text(
        json.dumps({"base": "#zzzzzz"}),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["theme-compile", str(bogus)])
    assert result.exit_code == 1
