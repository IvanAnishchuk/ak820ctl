"""Tests for per-key custom RGB lighting."""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003 — used at runtime (tmp_path fixture)
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ak820ctl.cli import app
from ak820ctl.hid import PACKET_SIZE, REPORT_ID
from ak820ctl.perkey import (
    CMD_CUSTOM_LIGHT,
    NUM_KEYS,
    NUM_PACKETS,
    build_perkey_data,
    parse_perkey_data,
    write_perkey,
)

# ── Data building ────────────────────────────────────────────────────────────


class TestBuildPerkeyData:
    def test_produces_9_packets(self) -> None:
        colors = [(0, 0, 0)] * NUM_KEYS
        packets = build_perkey_data(colors)
        assert len(packets) == NUM_PACKETS

    def test_packet_size(self) -> None:
        colors = [(0, 0, 0)] * NUM_KEYS
        packets = build_perkey_data(colors)
        for pkt in packets:
            assert len(pkt) == PACKET_SIZE

    def test_position_indices(self) -> None:
        colors = [(0, 0, 0)] * NUM_KEYS
        packets = build_perkey_data(colors)
        raw = b"".join(packets)
        for pos in range(NUM_KEYS):
            assert raw[pos * 4] == pos

    def test_colors_encoded(self) -> None:
        colors = [(0, 0, 0)] * NUM_KEYS
        colors[0] = (255, 128, 64)
        colors[5] = (10, 20, 30)
        packets = build_perkey_data(colors)
        raw = b"".join(packets)
        # Key 0
        assert raw[1] == 255
        assert raw[2] == 128
        assert raw[3] == 64
        # Key 5
        assert raw[5 * 4 + 1] == 10
        assert raw[5 * 4 + 2] == 20
        assert raw[5 * 4 + 3] == 30

    def test_wrong_count_raises(self) -> None:
        with pytest.raises(ValueError, match="Expected 144"):
            build_perkey_data([(0, 0, 0)] * 10)


# ── Data parsing ─────────────────────────────────────────────────────────────


class TestParsePerkeyData:
    def test_parses_144_colors(self) -> None:
        # Build fake packets with hidapi report ID prefix
        packets = []
        for _i in range(NUM_PACKETS):
            pkt = [0x00] + [0] * PACKET_SIZE  # report ID + 64 bytes
            packets.append(pkt)
        colors = parse_perkey_data(packets)
        assert len(colors) == NUM_KEYS

    def test_round_trip(self) -> None:
        original = [(i % 256, (i * 2) % 256, (i * 3) % 256) for i in range(NUM_KEYS)]
        packets = build_perkey_data(original)
        # Simulate hidapi: prepend report ID byte
        fake_response = [[0x00, *pkt] for pkt in packets]
        parsed = parse_perkey_data(fake_response)
        assert parsed == original


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
        dev = MagicMock()
        mock_open.return_value = dev

        colors = [(255, 0, 0)] * NUM_KEYS
        write_perkey(colors, brightness=3)

        mock_start.assert_called_once_with(dev)
        # 1 CMD_CUSTOM_LIGHT + 9 data packets = 10 send_command calls
        assert mock_send_cmd.call_count == 10
        # First call is CMD_CUSTOM_LIGHT
        first_pkt = mock_send_cmd.call_args_list[0][0][1]
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
        dev = MagicMock()
        write_perkey([(0, 0, 0)] * NUM_KEYS, device=dev)
        dev.close.assert_not_called()


# ── CLI tests ────────────────────────────────────────────────────────────────


class TestCli:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["perkey", "--help"])
        assert result.exit_code == 0
        assert "per-key" in result.output.lower() or "RGB" in result.output

    def test_dump_file_not_found(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["perkey", "--file", "/nonexistent/colors.json"])
        assert result.exit_code == 1
        assert "File not found" in result.output

    @patch("ak820ctl.perkey.open_device")
    @patch("ak820ctl.perkey.read_data")
    @patch("ak820ctl.perkey.send_report")
    @patch("ak820ctl.perkey.session_save")
    @patch("ak820ctl.perkey.session_end")
    def test_dump_json_output(
        self,
        _mock_end: MagicMock,
        _mock_save: MagicMock,
        _mock_send: MagicMock,
        mock_read: MagicMock,
        mock_open: MagicMock,
    ) -> None:
        dev = MagicMock()
        mock_open.return_value = dev
        # Return 9 packets of zeros (with report ID prefix)
        mock_read.return_value = [[0x00] + [0] * PACKET_SIZE for _ in range(NUM_PACKETS)]

        runner = CliRunner()
        result = runner.invoke(app, ["perkey", "--dump"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == NUM_KEYS

    @patch("ak820ctl.perkey.open_device")
    @patch("ak820ctl.perkey.set_lighting")
    @patch("ak820ctl.perkey.session_end")
    @patch("ak820ctl.perkey.session_save")
    @patch("ak820ctl.perkey.send_command")
    @patch("ak820ctl.perkey.session_start")
    def test_all_color(
        self,
        _mock_start: MagicMock,
        _mock_send: MagicMock,
        _mock_save: MagicMock,
        _mock_end: MagicMock,
        _mock_lighting: MagicMock,
        mock_open: MagicMock,
    ) -> None:
        mock_open.return_value = MagicMock()
        runner = CliRunner()
        result = runner.invoke(app, ["perkey", "--all", "ff0000"])
        assert result.exit_code == 0
        assert "144 keys set" in result.output.lower() or "set to" in result.output

    def test_file_load(self, tmp_path: Path) -> None:
        colors_file = tmp_path / "colors.json"
        data = [{"index": i, "r": 255, "g": 0, "b": 0} for i in range(NUM_KEYS)]
        colors_file.write_text(json.dumps(data))

        with (
            patch("ak820ctl.perkey.open_device") as mock_open,
            patch("ak820ctl.perkey.session_start"),
            patch("ak820ctl.perkey.send_command"),
            patch("ak820ctl.perkey.session_save"),
            patch("ak820ctl.perkey.session_end"),
            patch("ak820ctl.perkey.set_lighting"),
        ):
            mock_open.return_value = MagicMock()
            runner = CliRunner()
            result = runner.invoke(app, ["perkey", "--file", str(colors_file)])
            assert result.exit_code == 0
            assert "Loaded" in result.output
