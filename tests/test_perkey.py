"""Tests for per-key custom RGB lighting."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ak820ctl.cli import app
from ak820ctl.hid import PACKET_SIZE, REPORT_ID
from ak820ctl.models import KeyColor
from ak820ctl.perkey import (
    CMD_CUSTOM_LIGHT,
    NUM_KEYS,
    NUM_PACKETS,
    build_perkey_data,
    parse_perkey_data,
    write_perkey,
)
from tests.conftest import HidDeviceMock, as_hid_device

# ── Data building ────────────────────────────────────────────────────────────


class TestBuildPerkeyData:
    def _black_keys(self) -> list[KeyColor]:
        return [KeyColor(index=i) for i in range(NUM_KEYS)]

    def test_produces_9_packets(self) -> None:
        packets = build_perkey_data(self._black_keys())
        assert len(packets) == NUM_PACKETS

    def test_packet_size(self) -> None:
        packets = build_perkey_data(self._black_keys())
        for pkt in packets:
            assert len(pkt) == PACKET_SIZE

    def test_position_indices(self) -> None:
        packets = build_perkey_data(self._black_keys())
        raw = b"".join(packets)
        for pos in range(NUM_KEYS):
            assert raw[pos * 4] == pos

    def test_colors_encoded(self) -> None:
        keys = self._black_keys()
        keys[0] = KeyColor(index=0, r=255, g=128, b=64)
        keys[5] = KeyColor(index=5, r=10, g=20, b=30)
        packets = build_perkey_data(keys)
        raw = b"".join(packets)
        assert raw[1] == 255
        assert raw[2] == 128
        assert raw[3] == 64
        assert raw[5 * 4 + 1] == 10
        assert raw[5 * 4 + 2] == 20
        assert raw[5 * 4 + 3] == 30

    def test_wrong_count_raises(self) -> None:
        with pytest.raises(ValueError, match="Expected 144"):
            _ = build_perkey_data([KeyColor(index=0)] * 10)


# ── Data parsing ─────────────────────────────────────────────────────────────


class TestParsePerkeyData:
    def test_parses_144_keys(self) -> None:
        packets = [[0x00] + [0] * PACKET_SIZE for _ in range(NUM_PACKETS)]
        keys = parse_perkey_data(packets)
        assert len(keys) == NUM_KEYS
        assert all(isinstance(k, KeyColor) for k in keys)

    def test_round_trip(self) -> None:
        original = [
            KeyColor(index=i, r=i % 256, g=(i * 2) % 256, b=(i * 3) % 256) for i in range(NUM_KEYS)
        ]
        packets = build_perkey_data(original)
        fake_response = [[0x00, *pkt] for pkt in packets]
        parsed = parse_perkey_data(fake_response)
        for orig, got in zip(original, parsed, strict=True):
            assert (orig.r, orig.g, orig.b) == (got.r, got.g, got.b)


# ── Write protocol ───────────────────────────────────────────────────────────


class TestWritePerkey:
    @patch("ak820ctl.perkey.set_lighting")
    @patch("ak820ctl.perkey.session_end")
    @patch("ak820ctl.perkey.session_save")
    @patch("ak820ctl.perkey.send_command")
    @patch("ak820ctl.perkey.session_start")
    @patch("ak820ctl.perkey.open_device")
    def test_write_sequence(
        self,
        mock_open: MagicMock,
        mock_start: MagicMock,
        mock_send_cmd: MagicMock,
        mock_save: MagicMock,
        mock_end: MagicMock,
        mock_set_lighting: MagicMock,
    ) -> None:
        dev = HidDeviceMock()
        mock_open.return_value = as_hid_device(dev)

        keys = [KeyColor(index=i, r=255) for i in range(NUM_KEYS)]
        write_perkey(keys, brightness=3)

        mock_start.assert_called_once_with(dev)
        # 1 CMD_CUSTOM_LIGHT + 9 data packets = 10
        assert mock_send_cmd.call_count == 10
        first_pkt = cast("list[int]", mock_send_cmd.call_args_list[0][0][1])
        assert first_pkt[0] == REPORT_ID
        assert first_pkt[1] == CMD_CUSTOM_LIGHT
        assert first_pkt[8] == 0x09
        mock_save.assert_called_once()
        mock_end.assert_called_once()
        mock_set_lighting.assert_called_once_with(dev, mode="custom", brightness=3)
        dev.close.assert_called_once()

    @patch("ak820ctl.perkey.set_lighting")
    @patch("ak820ctl.perkey.session_end")
    @patch("ak820ctl.perkey.session_save")
    @patch("ak820ctl.perkey.send_command")
    @patch("ak820ctl.perkey.session_start")
    def test_provided_device_not_closed(
        self,
        _mock_start: MagicMock,
        _mock_send_cmd: MagicMock,
        _mock_save: MagicMock,
        _mock_end: MagicMock,
        _mock_set_lighting: MagicMock,
    ) -> None:
        dev = HidDeviceMock()
        write_perkey([KeyColor(index=i) for i in range(NUM_KEYS)], device=as_hid_device(dev))
        dev.close.assert_not_called()


# ── CLI tests ────────────────────────────────────────────────────────────────


class TestCli:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["perkey", "--help"])
        assert result.exit_code == 0

    def test_load_not_found(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["perkey", "--load", "/nonexistent/colors.json"])
        assert result.exit_code == 1

    @patch("ak820ctl.perkey.open_device")
    @patch("ak820ctl.perkey.read_data")
    @patch("ak820ctl.perkey.send_report")
    @patch("ak820ctl.perkey.session_save")
    @patch("ak820ctl.perkey.session_end")
    def test_dump_produces_valid_json(
        self,
        _mock_end: MagicMock,
        _mock_save: MagicMock,
        _mock_send: MagicMock,
        mock_read: MagicMock,
        mock_open: MagicMock,
    ) -> None:
        mock_open.return_value = as_hid_device(HidDeviceMock())
        mock_read.return_value = [[0x00] + [0] * PACKET_SIZE for _ in range(NUM_PACKETS)]

        runner = CliRunner()
        result = runner.invoke(app, ["perkey", "--dump"])
        assert result.exit_code == 0
        data = cast("list[dict[str, int]]", json.loads(result.output))
        assert len(data) == NUM_KEYS
        assert set(data[0].keys()) >= {"index", "r", "g", "b"}

    @patch("ak820ctl.perkey.open_device")
    @patch("ak820ctl.perkey.set_lighting")
    @patch("ak820ctl.perkey.session_end")
    @patch("ak820ctl.perkey.session_save")
    @patch("ak820ctl.perkey.send_command")
    @patch("ak820ctl.perkey.session_start")
    def test_all_color_succeeds(
        self,
        _mock_start: MagicMock,
        _mock_send: MagicMock,
        _mock_save: MagicMock,
        _mock_end: MagicMock,
        _mock_lighting: MagicMock,
        mock_open: MagicMock,
    ) -> None:
        mock_open.return_value = as_hid_device(HidDeviceMock())
        runner = CliRunner()
        result = runner.invoke(app, ["perkey", "--all", "ff0000"])
        assert result.exit_code == 0

    def test_load_succeeds(self, tmp_path: Path) -> None:
        colors_file = tmp_path / "colors.json"
        data = [{"index": i, "r": 255, "g": 0, "b": 0} for i in range(NUM_KEYS)]
        _ = colors_file.write_text(json.dumps(data))

        with (
            patch("ak820ctl.perkey.open_device") as mock_open,
            patch("ak820ctl.perkey.session_start"),
            patch("ak820ctl.perkey.send_command"),
            patch("ak820ctl.perkey.session_save"),
            patch("ak820ctl.perkey.session_end"),
            patch("ak820ctl.perkey.set_lighting"),
        ):
            mock_open.return_value = as_hid_device(HidDeviceMock())
            result = CliRunner().invoke(app, ["perkey", "--load", str(colors_file)])
            assert result.exit_code == 0

    @patch("ak820ctl.perkey.open_device")
    @patch("ak820ctl.perkey.read_data")
    @patch("ak820ctl.perkey.send_report")
    @patch("ak820ctl.perkey.session_save")
    @patch("ak820ctl.perkey.session_end")
    def test_save_writes_valid_json(
        self,
        _mock_end: MagicMock,
        _mock_save: MagicMock,
        _mock_send: MagicMock,
        mock_read: MagicMock,
        mock_open: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_open.return_value = as_hid_device(HidDeviceMock())
        # Build mock response with known colors
        keys = [
            KeyColor(index=i, r=i % 256, g=(i * 2) % 256, b=(i * 3) % 256) for i in range(NUM_KEYS)
        ]
        packets = build_perkey_data(keys)
        mock_read.return_value = [[0x00, *pkt] for pkt in packets]

        out_file = tmp_path / "saved.json"
        runner = CliRunner()
        result = runner.invoke(app, ["perkey", "--save", str(out_file)])
        assert result.exit_code == 0

        data = cast("list[dict[str, int]]", json.loads(out_file.read_text()))
        assert len(data) == NUM_KEYS
        assert data[0]["r"] == 0
        assert data[5]["r"] == 5
        assert data[5]["g"] == 10
        assert data[5]["b"] == 15

    def test_save_load_round_trip(self, tmp_path: Path) -> None:
        """Verify that --save output can be loaded back via --load identically."""
        # Build mock HID response with varied colors
        keys = [
            KeyColor(index=i, r=i % 256, g=(i * 2) % 256, b=(i * 3) % 256) for i in range(NUM_KEYS)
        ]
        packets = build_perkey_data(keys)
        mock_response = [[0x00, *pkt] for pkt in packets]

        out_file = tmp_path / "round_trip.json"

        # Step 1: Save
        with (
            patch("ak820ctl.perkey.open_device") as mock_open,
            patch("ak820ctl.perkey.read_data") as mock_read,
            patch("ak820ctl.perkey.send_report"),
            patch("ak820ctl.perkey.session_save"),
            patch("ak820ctl.perkey.session_end"),
        ):
            mock_open.return_value = as_hid_device(HidDeviceMock())
            mock_read.return_value = mock_response
            runner = CliRunner()
            result = runner.invoke(app, ["perkey", "--save", str(out_file)])
            assert result.exit_code == 0

        # Step 2: Load back and verify data sent to device matches original
        with (
            patch("ak820ctl.perkey.open_device") as mock_open,
            patch("ak820ctl.perkey.session_start"),
            patch("ak820ctl.perkey.send_command") as mock_send,
            patch("ak820ctl.perkey.session_save"),
            patch("ak820ctl.perkey.session_end"),
            patch("ak820ctl.perkey.set_lighting"),
        ):
            mock_open.return_value = as_hid_device(HidDeviceMock())
            runner = CliRunner()
            result = runner.invoke(app, ["perkey", "--load", str(out_file)])
            assert result.exit_code == 0

            # send_command is called 1 (CMD) + 9 (data) = 10 times
            assert mock_send.call_count == 10
            # Reconstruct data packets sent to device (calls 1-9)
            sent_packets = [mock_send.call_args_list[i + 1][0][1] for i in range(NUM_PACKETS)]
            sent_raw = b"".join(sent_packets)
            for i in range(NUM_KEYS):
                off = i * 4
                assert sent_raw[off + 1] == i % 256  # r
                assert sent_raw[off + 2] == (i * 2) % 256  # g
                assert sent_raw[off + 3] == (i * 3) % 256  # b

    @pytest.mark.parametrize("example", ["groups-basic", "groups-rainbow", "rows-stealth"])
    def test_load_example_files(self, example: str) -> None:
        """Verify bundled example JSON files are valid and loadable."""
        example_path = Path(__file__).parent.parent / "examples" / "perkey" / f"{example}.json"
        assert example_path.exists(), f"Example file not found: {example_path}"

        data = cast("list[dict[str, int]]", json.loads(example_path.read_text()))
        assert len(data) == NUM_KEYS
        for entry in data:
            assert 0 <= entry["index"] <= 143
            assert 0 <= entry["r"] <= 255
            assert 0 <= entry["g"] <= 255
            assert 0 <= entry["b"] <= 255
