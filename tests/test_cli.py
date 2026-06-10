"""Tests for the CLI."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ak820ctl.cli import app, parse_hex_color, parse_key_spec
from ak820ctl.models import DeviceInfo, KeyboardDump, KeyColor, LightingConfig
from ak820ctl.perkey import NUM_KEYS

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
    _ = bogus.write_text(
        json.dumps({"base": "#000000", "groups": {"not_a_real_group": "#ff0000"}}),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["theme-compile", str(bogus)])
    assert result.exit_code == 1
    assert "not_a_real_group" in result.output


def test_theme_compile_unknown_override(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus.json"
    _ = bogus.write_text(
        json.dumps({"base": "#000000", "overrides": {"not_a_key": "#ff0000"}}),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["theme-compile", str(bogus)])
    assert result.exit_code == 1
    assert "not_a_key" in result.output


def test_theme_compile_hex_without_hash_rejected(tmp_path: Path) -> None:
    """HexColor validation requires a leading '#'."""
    bogus = tmp_path / "bogus.json"
    _ = bogus.write_text(json.dumps({"base": "ff0000"}), encoding="utf-8")
    result = runner.invoke(app, ["theme-compile", str(bogus)])
    assert result.exit_code == 1


def test_theme_compile_malformed_hex(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus.json"
    _ = bogus.write_text(
        json.dumps({"base": "#zzzzzz"}),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["theme-compile", str(bogus)])
    assert result.exit_code == 1


# ---------------------------- stdin/stdout via `-` ----------------------------


def test_theme_compile_dash_output_writes_to_stdout() -> None:
    """`-o -` is explicit stdout and should match the no-`-o` default."""
    src = THEMES_DIR / "groups-solarized-theme.json"
    expected = (COMPILED_DIR / "groups-solarized.json").read_text(encoding="utf-8")
    result = runner.invoke(app, ["theme-compile", str(src), "-o", "-"])
    assert result.exit_code == 0
    assert result.output == expected


def test_theme_compile_dash_source_reads_from_stdin() -> None:
    """`source = -` reads theme JSON from stdin."""
    src = THEMES_DIR / "groups-solarized-theme.json"
    expected = (COMPILED_DIR / "groups-solarized.json").read_text(encoding="utf-8")
    result = runner.invoke(app, ["theme-compile", "-"], input=src.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert result.output == expected


def test_theme_compile_dash_source_and_dash_output_pipeline() -> None:
    """Full `-` → `-` pipeline: stdin source, stdout output."""
    src = THEMES_DIR / "groups-basic-theme.json"
    expected = (COMPILED_DIR / "groups-basic.json").read_text(encoding="utf-8")
    result = runner.invoke(
        app, ["theme-compile", "-", "-o", "-"], input=src.read_text(encoding="utf-8")
    )
    assert result.exit_code == 0
    assert result.output == expected


def _all_red_payload() -> str:
    return json.dumps([{"index": i, "r": 255, "g": 0, "b": 0} for i in range(NUM_KEYS)])


@patch("ak820ctl.cli.write_perkey")
def test_perkey_load_dash_reads_colors_from_stdin(mock_write: MagicMock) -> None:
    """`perkey --load -` reads per-key JSON from stdin and writes it."""
    result = runner.invoke(app, ["perkey", "--load", "-"], input=_all_red_payload())
    assert result.exit_code == 0, result.output
    assert "Loaded per-key colors from stdin" in result.output
    mock_write.assert_called_once()
    keys_arg = cast("list[KeyColor]", mock_write.call_args.args[0])
    assert len(keys_arg) == NUM_KEYS
    assert all(k.r == 255 and k.g == 0 and k.b == 0 for k in keys_arg)


@patch("ak820ctl.cli.read_perkey_live")
def test_perkey_save_dash_writes_to_stdout(mock_read: MagicMock) -> None:
    """`perkey --save -` prints live per-key state to stdout instead of a file."""
    mock_read.return_value = [KeyColor(index=i, r=1, g=2, b=3) for i in range(NUM_KEYS)]
    result = runner.invoke(app, ["perkey", "--save", "-"])
    assert result.exit_code == 0
    data = cast("list[dict[str, int]]", json.loads(result.output))
    assert len(data) == NUM_KEYS
    assert data[0] == {"index": 0, "r": 1, "g": 2, "b": 3}
    # No "saved to" banner when writing to stdout.
    assert "saved to" not in result.output


# ---------------------------- parse helpers ----------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ff0000", (255, 0, 0)),
        ("#00ff00", (0, 255, 0)),
        ("0000FF", (0, 0, 255)),
        ("#aabbcc", (0xAA, 0xBB, 0xCC)),
    ],
)
def test_parse_hex_color_accepts_valid(text: str, expected: tuple[int, int, int]) -> None:
    assert parse_hex_color(text) == expected


@pytest.mark.parametrize("bad", ["fff", "ff00", "#zzzzzz", "", "ff00000"])
def test_parse_hex_color_rejects_invalid(bad: str) -> None:
    if bad == "#zzzzzz":
        # right length, wrong chars — int() raises ValueError too
        with pytest.raises(ValueError):
            _ = parse_hex_color(bad)
    else:
        with pytest.raises(ValueError, match="6 hex digits"):
            _ = parse_hex_color(bad)


def test_parse_key_spec_valid() -> None:
    assert parse_key_spec("42:ff0000", NUM_KEYS) == (42, (255, 0, 0))


@pytest.mark.parametrize(
    ("bad", "match"),
    [
        ("42ff0000", "expected INDEX:RRGGBB"),
        ("144:ff0000", "0-143"),
        ("-1:ff0000", "0-143"),
    ],
)
def test_parse_key_spec_rejects(bad: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        _ = parse_key_spec(bad, NUM_KEYS)


# ---------------------------- perkey command modes ----------------------------


@patch("ak820ctl.cli.write_perkey")
def test_perkey_all_sets_every_key(mock_write: MagicMock) -> None:
    result = runner.invoke(app, ["perkey", "--all", "ff8800", "-b", "3"])
    assert result.exit_code == 0, result.output
    keys = cast("list[KeyColor]", mock_write.call_args.args[0])
    assert len(keys) == NUM_KEYS
    assert all(k.r == 0xFF and k.g == 0x88 and k.b == 0x00 for k in keys)
    assert mock_write.call_args.kwargs["brightness"] == 3


@patch("ak820ctl.cli.write_perkey")
@patch("ak820ctl.cli.read_perkey_live")
def test_perkey_key_overrides_specific_indices(
    mock_read: MagicMock,
    mock_write: MagicMock,
) -> None:
    mock_read.return_value = [KeyColor(index=i) for i in range(NUM_KEYS)]
    result = runner.invoke(app, ["perkey", "-k", "5:ff0000", "-k", "7:00ff00"])
    assert result.exit_code == 0, result.output
    keys = cast("list[KeyColor]", mock_write.call_args.args[0])
    assert keys[5].r == 255 and keys[5].g == 0
    assert keys[7].g == 255 and keys[7].r == 0
    assert keys[0].r == 0 and keys[0].g == 0


def test_perkey_all_invalid_hex_exits_with_error() -> None:
    result = runner.invoke(app, ["perkey", "--all", "xyz"])
    assert result.exit_code == 1
    assert "6 hex digits" in result.output


def test_perkey_key_malformed_spec_exits_with_error() -> None:
    result = runner.invoke(app, ["perkey", "-k", "no-colon"])
    assert result.exit_code == 1
    assert "INDEX:RRGGBB" in result.output


@patch("ak820ctl.cli.read_perkey_live")
def test_perkey_dump_prints_json(mock_read: MagicMock) -> None:
    mock_read.return_value = [KeyColor(index=i, r=10, g=20, b=30) for i in range(NUM_KEYS)]
    result = runner.invoke(app, ["perkey", "--dump"])
    assert result.exit_code == 0
    data = cast("list[dict[str, int]]", json.loads(result.output))
    assert len(data) == NUM_KEYS
    assert data[0] == {"index": 0, "r": 10, "g": 20, "b": 30}


@patch("ak820ctl.cli.read_perkey_stored")
def test_perkey_dump_stored_prints_json(mock_read_stored: MagicMock) -> None:
    mock_read_stored.return_value = [KeyColor(index=i, r=5, g=5, b=5) for i in range(NUM_KEYS)]
    result = runner.invoke(app, ["perkey", "--dump-stored"])
    assert result.exit_code == 0
    data = cast("list[dict[str, int]]", json.loads(result.output))
    assert data[0]["r"] == 5


@patch("ak820ctl.cli.read_perkey_live")
def test_perkey_no_args_shows_no_active_when_all_black(mock_read: MagicMock) -> None:
    mock_read.return_value = [KeyColor(index=i) for i in range(NUM_KEYS)]
    result = runner.invoke(app, ["perkey"])
    assert result.exit_code == 0
    assert "No per-key colors active" in result.output


@patch("ak820ctl.cli.read_perkey_live")
def test_perkey_no_args_lists_active_keys(mock_read: MagicMock) -> None:
    keys = [KeyColor(index=i) for i in range(NUM_KEYS)]
    keys[3] = KeyColor(index=3, r=255, g=0, b=0)
    keys[42] = KeyColor(index=42, r=0, g=255, b=0)
    mock_read.return_value = keys
    result = runner.invoke(app, ["perkey"])
    assert result.exit_code == 0
    assert "2 key(s) with color" in result.output
    assert "ff0000" in result.output
    assert "00ff00" in result.output


def test_perkey_load_missing_file_exits_with_error() -> None:
    result = runner.invoke(app, ["perkey", "--load", "/nonexistent/whatever.json"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


@patch("ak820ctl.cli.read_perkey_live")
def test_perkey_save_writes_to_file(mock_read: MagicMock, tmp_path: Path) -> None:
    mock_read.return_value = [KeyColor(index=i, r=7, g=8, b=9) for i in range(NUM_KEYS)]
    out = tmp_path / "saved.json"
    result = runner.invoke(app, ["perkey", "--save", str(out)])
    assert result.exit_code == 0
    assert "saved to" in result.output.lower()
    data = cast("list[dict[str, int]]", json.loads(out.read_text(encoding="utf-8")))
    assert len(data) == NUM_KEYS
    assert data[0] == {"index": 0, "r": 7, "g": 8, "b": 9}


# ---------------------------- time ----------------------------


@patch("ak820ctl.cli.sync_time")
def test_time_set_with_full_datetime(mock_sync: MagicMock) -> None:
    """`time --set "YYYY-MM-DD HH:MM:SS"` parses to datetime and passes through."""
    expected = datetime(2025, 3, 15, 14, 30, 45)
    mock_sync.return_value = expected
    result = runner.invoke(app, ["time", "--set", "2025-03-15 14:30:45"])
    assert result.exit_code == 0
    assert "Clock synced" in result.output
    assert mock_sync.call_args.kwargs["dt"] == expected


@patch("ak820ctl.cli.sync_time")
@patch("ak820ctl.cli.datetime")
def test_time_set_with_time_only_uses_today(mock_dt: MagicMock, mock_sync: MagicMock) -> None:
    """`time --set HH:MM:SS` parses with today's date filled in.

    `datetime.now()` is patched to a fixed value so the test can't flake
    across a midnight rollover between the test capture and the CLI call.
    """
    fixed = datetime(2025, 6, 11, 12, 0, 0)
    mock_dt.now.return_value = fixed
    mock_dt.strptime.side_effect = datetime.strptime
    mock_sync.return_value = fixed
    result = runner.invoke(app, ["time", "--set", "14:30:45"])
    assert result.exit_code == 0
    dt_arg = cast("datetime", mock_sync.call_args.kwargs["dt"])
    assert (dt_arg.year, dt_arg.month, dt_arg.day) == (2025, 6, 11)
    assert (dt_arg.hour, dt_arg.minute, dt_arg.second) == (14, 30, 45)


@patch("ak820ctl.cli.sync_time")
def test_time_no_args_syncs_now(mock_sync: MagicMock) -> None:
    """`time` with no args calls sync_time with dt=None (use system clock)."""
    mock_sync.return_value = datetime.now()
    result = runner.invoke(app, ["time"])
    assert result.exit_code == 0
    assert mock_sync.call_args.kwargs["dt"] is None


@patch("ak820ctl.cli.sync_time", side_effect=RuntimeError("no device"))
def test_time_runtime_error_exits_1(mock_sync: MagicMock) -> None:
    del mock_sync
    result = runner.invoke(app, ["time"])
    assert result.exit_code == 1
    assert "no device" in result.output


# ---------------------------- light ----------------------------


@patch("ak820ctl.cli.read_lighting")
def test_light_show_displays_config(mock_read: MagicMock) -> None:
    mock_read.return_value = LightingConfig(
        mode="breath", r=0xFF, g=0x80, b=0x00, brightness=4, speed=2, direction="up", rainbow=True
    )
    result = runner.invoke(app, ["light", "--show"])
    assert result.exit_code == 0
    assert "breath" in result.output
    assert "#ff8000" in result.output
    assert "up" in result.output


@patch("ak820ctl.cli.set_lighting")
def test_light_static_set_succeeds(mock_set: MagicMock) -> None:
    result = runner.invoke(app, ["light", "static", "--color", "ff8800", "--brightness", "4"])
    assert result.exit_code == 0
    assert "Lighting set" in result.output
    assert mock_set.call_args.kwargs["mode"] == "static"
    assert mock_set.call_args.kwargs["r"] == 0xFF
    assert mock_set.call_args.kwargs["g"] == 0x88
    assert mock_set.call_args.kwargs["b"] == 0x00
    assert mock_set.call_args.kwargs["brightness"] == 4


@patch("ak820ctl.cli.read_lighting", side_effect=RuntimeError("comm failure"))
def test_light_show_runtime_error_exits_1(mock_read: MagicMock) -> None:
    del mock_read
    result = runner.invoke(app, ["light", "--show"])
    assert result.exit_code == 1
    assert "comm failure" in result.output


@patch("ak820ctl.cli.set_lighting", side_effect=RuntimeError("no device"))
def test_light_set_runtime_error_exits_1(mock_set: MagicMock) -> None:
    del mock_set
    result = runner.invoke(app, ["light", "static", "--color", "ff0000"])
    assert result.exit_code == 1
    assert "no device" in result.output


# ---------------------------- sleep ----------------------------


@patch("ak820ctl.cli.set_sleep")
def test_sleep_succeeds(mock_set: MagicMock) -> None:
    result = runner.invoke(app, ["sleep", "5min"])
    assert result.exit_code == 0
    assert "Sleep timer set" in result.output
    assert mock_set.call_args.kwargs["timeout"] == "5min"


@patch("ak820ctl.cli.set_sleep", side_effect=RuntimeError("no device"))
def test_sleep_runtime_error_exits_1(mock_set: MagicMock) -> None:
    del mock_set
    result = runner.invoke(app, ["sleep", "1min"])
    assert result.exit_code == 1
    assert "no device" in result.output


# ---------------------------- info ----------------------------


@patch("ak820ctl.cli.get_device_info")
@patch("ak820ctl.cli.find_device")
def test_info_succeeds_prints_firmware(mock_find: MagicMock, mock_info: MagicMock) -> None:
    mock_find.return_value = b"/dev/hidraw3"
    mock_info.return_value = DeviceInfo(vid=0x0C45, pid=0x8009, firmware="1.20")
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "Found AK820" in result.output
    assert "/dev/hidraw3" in result.output
    assert "v1.20" in result.output


# ---------------------------- dump ----------------------------


@patch("ak820ctl.cli.dump_settings")
def test_dump_to_stdout(mock_dump: MagicMock) -> None:
    mock_dump.return_value = KeyboardDump(
        device=DeviceInfo(vid=0x0C45, pid=0x8009, firmware="1.20"),
        lighting=LightingConfig(mode="static", r=0xFF),
    )
    result = runner.invoke(app, ["dump"])
    assert result.exit_code == 0
    assert "1.20" in result.output
    assert "static" in result.output


@patch("ak820ctl.cli.dump_settings")
def test_dump_to_file_writes_json(mock_dump: MagicMock, tmp_path: Path) -> None:
    mock_dump.return_value = KeyboardDump(
        device=DeviceInfo(vid=0x0C45, pid=0x8009, firmware="1.20"),
        lighting=LightingConfig(mode="breath"),
    )
    out = tmp_path / "settings.json"
    result = runner.invoke(app, ["dump", "-o", str(out)])
    assert result.exit_code == 0
    assert "saved to" in result.output.lower()
    data = cast("dict[str, dict[str, object]]", json.loads(out.read_text(encoding="utf-8")))
    assert data["device"]["firmware"] == "1.20"
    assert data["lighting"]["mode"] == "breath"


@patch("ak820ctl.cli.dump_settings", side_effect=RuntimeError("no device"))
def test_dump_runtime_error_exits_1(mock_dump: MagicMock) -> None:
    del mock_dump
    result = runner.invoke(app, ["dump"])
    assert result.exit_code == 1
    assert "no device" in result.output


# ---------------------------- image ----------------------------


@patch("ak820ctl.cli.upload_image")
@patch("ak820ctl.cli.load_image")
def test_image_succeeds(mock_load: MagicMock, mock_upload: MagicMock, tmp_path: Path) -> None:
    """`image FILE` calls load_image, then upload_image with the bytes and slot."""
    f = tmp_path / "smile.png"
    _ = f.write_bytes(b"fake png bytes")
    mock_load.return_value = b"\x00" * 1024  # any non-empty bytes
    result = runner.invoke(app, ["image", str(f), "--slot", "2"])
    assert result.exit_code == 0, result.output
    assert "Image uploaded to slot 2" in result.output
    mock_load.assert_called_once_with(f)
    assert mock_upload.call_args.kwargs["slot"] == 2


def test_image_slot_out_of_range(tmp_path: Path) -> None:
    f = tmp_path / "img.png"
    _ = f.write_bytes(b"x")
    result = runner.invoke(app, ["image", str(f), "--slot", "0"])
    assert result.exit_code == 1
    assert "Slot must be 1-255" in result.output


@patch("ak820ctl.cli.load_image", side_effect=OSError("bad file"))
def test_image_oserror_on_load(mock_load: MagicMock, tmp_path: Path) -> None:
    del mock_load
    f = tmp_path / "img.png"
    _ = f.write_bytes(b"x")
    result = runner.invoke(app, ["image", str(f)])
    assert result.exit_code == 1
    assert "Cannot load image" in result.output


@patch("ak820ctl.cli.upload_image", side_effect=RuntimeError("no device"))
@patch("ak820ctl.cli.load_image")
def test_image_runtime_error_exits_1(
    mock_load: MagicMock, mock_upload: MagicMock, tmp_path: Path
) -> None:
    del mock_upload
    mock_load.return_value = b"\x00" * 1024
    f = tmp_path / "img.png"
    _ = f.write_bytes(b"x")
    result = runner.invoke(app, ["image", str(f)])
    assert result.exit_code == 1
    assert "no device" in result.output


# ---------------------------- gif ----------------------------


@patch("ak820ctl.cli.upload_image")
@patch("ak820ctl.cli.load_animation")
def test_gif_succeeds(mock_load: MagicMock, mock_upload: MagicMock, tmp_path: Path) -> None:
    """`gif FILE` calls load_animation, then upload_image; prints frame count."""
    f = tmp_path / "anim.gif"
    _ = f.write_bytes(b"fake gif")
    # data[0] is frame count; load_animation returns header + frames
    mock_load.return_value = bytes([7]) + b"\x00" * 4096
    result = runner.invoke(app, ["gif", str(f), "--slot", "3"])
    assert result.exit_code == 0, result.output
    assert "Loaded 7 frame" in result.output
    assert "uploaded to slot 3" in result.output
    assert mock_upload.call_args.kwargs["slot"] == 3


def test_gif_slot_out_of_range(tmp_path: Path) -> None:
    f = tmp_path / "anim.gif"
    _ = f.write_bytes(b"x")
    result = runner.invoke(app, ["gif", str(f), "--slot", "300"])
    assert result.exit_code == 1
    assert "Slot must be 1-255" in result.output


def test_gif_max_frames_zero_rejected(tmp_path: Path) -> None:
    f = tmp_path / "anim.gif"
    _ = f.write_bytes(b"x")
    result = runner.invoke(app, ["gif", str(f), "--max-frames", "0"])
    assert result.exit_code == 1
    assert "max-frames must be >= 1" in result.output


@patch("ak820ctl.cli.load_animation", side_effect=OSError("bad gif"))
def test_gif_oserror_on_load(mock_load: MagicMock, tmp_path: Path) -> None:
    del mock_load
    f = tmp_path / "anim.gif"
    _ = f.write_bytes(b"x")
    result = runner.invoke(app, ["gif", str(f)])
    assert result.exit_code == 1
    assert "Cannot load animation" in result.output


# ---------------------------- restore ----------------------------


@patch("ak820ctl.cli.restore_settings")
def test_restore_succeeds(mock_restore: MagicMock, tmp_path: Path) -> None:
    """`restore FILE` reads JSON, calls restore_settings, prints actions."""
    dump = KeyboardDump(
        device=DeviceInfo(vid=0x0C45, pid=0x8009, firmware="1.20"),
        lighting=LightingConfig(mode="breath"),
    )
    f = tmp_path / "backup.json"
    dump.save(f)
    mock_restore.return_value = ["time: synced", "lighting: breath"]
    result = runner.invoke(app, ["restore", str(f)])
    assert result.exit_code == 0
    assert "time: synced" in result.output
    assert "lighting: breath" in result.output
    assert mock_restore.call_args.kwargs["skip_time"] is False


@patch("ak820ctl.cli.restore_settings")
def test_restore_skip_time_passes_through(mock_restore: MagicMock, tmp_path: Path) -> None:
    dump = KeyboardDump(lighting=LightingConfig(mode="off"))
    f = tmp_path / "backup.json"
    dump.save(f)
    mock_restore.return_value = ["lighting: off"]
    result = runner.invoke(app, ["restore", str(f), "--skip-time"])
    assert result.exit_code == 0
    assert mock_restore.call_args.kwargs["skip_time"] is True


def test_restore_missing_file_exits_1() -> None:
    result = runner.invoke(app, ["restore", "/nonexistent/backup.json"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_restore_invalid_json_exits_1(tmp_path: Path) -> None:
    f = tmp_path / "bad.json"
    _ = f.write_text("not json", encoding="utf-8")
    result = runner.invoke(app, ["restore", str(f)])
    assert result.exit_code == 1
    assert "Cannot read dump file" in result.output


@patch("ak820ctl.cli.restore_settings", side_effect=RuntimeError("no device"))
def test_restore_runtime_error_exits_1(mock_restore: MagicMock, tmp_path: Path) -> None:
    del mock_restore
    dump = KeyboardDump(lighting=LightingConfig(mode="off"))
    f = tmp_path / "backup.json"
    dump.save(f)
    result = runner.invoke(app, ["restore", str(f)])
    assert result.exit_code == 1
    assert "no device" in result.output
