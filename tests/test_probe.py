"""Tests for the `probe` CLI subcommand."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ak820ctl.cli import (
    PROBE_COUNTS,
    PROBE_DEFAULT_COUNT,
    PROBE_DESTRUCTIVE_CMDS,
    PROBE_SAFE_CMDS,
    app,
    format_probe_summary,
    probe_one,
    write_probe_response,
)
from tests.conftest import HidDeviceMock, as_hid_device

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


class TestProbeRefusals:
    def test_no_args_exits_1(self) -> None:
        result = runner.invoke(app, ["probe"])
        assert result.exit_code == 1
        assert "No action selected" in result.output

    def test_invalid_hex_exits_1(self) -> None:
        result = runner.invoke(app, ["probe", "--cmd", "notahex"])
        assert result.exit_code == 1
        assert "Invalid hex" in result.output

    def test_destructive_cmd_refused(self) -> None:
        # 0x13 = CMD_SET_LIGHTING — writes flash
        result = runner.invoke(app, ["probe", "--cmd", "0x13"])
        assert result.exit_code == 1
        assert "Refusing destructive CMD 0x13" in result.output
        assert "writes flash" in result.output

    def test_every_destructive_cmd_is_refused(self) -> None:
        # Sanity: every entry in PROBE_DESTRUCTIVE_CMDS is rejected by the CLI.
        for cmd_byte in PROBE_DESTRUCTIVE_CMDS:
            result = runner.invoke(app, ["probe", "--cmd", f"0x{cmd_byte:02x}"])
            assert result.exit_code == 1, f"CMD 0x{cmd_byte:02x} should have been refused"
            assert "Refusing destructive" in result.output

    def test_non_whitelisted_safe_cmd_refused(self) -> None:
        # 0x42 is neither whitelisted nor destructive — should be rejected
        # with the whitelist printed.
        result = runner.invoke(app, ["probe", "--cmd", "0x42"])
        assert result.exit_code == 1
        assert "not in the safe whitelist" in result.output


class TestProbeSingle:
    @patch("ak820ctl.cli.open_device")
    def test_cmd_single_succeeds(self, mock_open: MagicMock) -> None:
        dev = HidDeviceMock()
        # Return two non-empty packets, then nothing.
        dev.get_feature_report.side_effect = [
            [0x00] * 65,  # ACK discarded
            [0x00] + [0x42] * 64,
            [0x00] + [0x99] * 64,
            *([OSError("done")] * 10),
        ]
        mock_open.return_value = as_hid_device(dev)

        result = runner.invoke(app, ["probe", "--cmd", "0x05"])
        assert result.exit_code == 0, result.output
        assert "CMD 0x05" in result.output
        # First-byte preview of the first packet's payload should appear as hex.
        assert "42" in result.output
        dev.close.assert_called_once()


class TestProbeAll:
    @patch("ak820ctl.cli.open_device")
    def test_all_iterates_whitelist(self, mock_open: MagicMock) -> None:
        dev = HidDeviceMock()
        # 8 whitelist entries x (1 ACK + 1 data) = 16 calls minimum; pad with
        # OSErrors so the read loop ends cleanly each time.
        dev.get_feature_report.return_value = [0x00] * 65
        mock_open.return_value = as_hid_device(dev)

        result = runner.invoke(app, ["probe", "--all"])
        assert result.exit_code == 0, result.output
        for cmd_byte in PROBE_SAFE_CMDS:
            assert f"CMD 0x{cmd_byte:02x}" in result.output

    @patch("ak820ctl.cli.open_device")
    def test_output_dir_writes_one_file_per_cmd(self, mock_open: MagicMock, tmp_path: Path) -> None:
        dev = HidDeviceMock()
        dev.get_feature_report.return_value = [0x00] * 65
        mock_open.return_value = as_hid_device(dev)
        out = tmp_path / "probe_out"

        result = runner.invoke(app, ["probe", "--all", "--output-dir", str(out)])
        assert result.exit_code == 0, result.output
        assert out.is_dir()
        for cmd_byte in PROBE_SAFE_CMDS:
            p = out / f"cmd_{cmd_byte:02x}.bin"
            assert p.exists(), f"missing {p}"

    @patch("ak820ctl.cli.open_device", side_effect=RuntimeError("no device"))
    def test_runtime_error_per_cmd_logs_but_continues(self, _mock_open: MagicMock) -> None:
        # Every probe call raises RuntimeError; the loop must keep iterating
        # so a single dead CMD doesn't kill the rest of the report.
        result = runner.invoke(app, ["probe", "--all"])
        # Exit 0 because individual failures are logged and the loop continues.
        assert result.exit_code == 0
        for cmd_byte in PROBE_SAFE_CMDS:
            assert f"CMD 0x{cmd_byte:02x} failed" in result.output


class TestProbeOutputFormatting:
    def test_format_summary_includes_packet_count_and_hex_head(self) -> None:
        packets = [[0, *list(range(64))], [0, *([0xFF] * 64)]]
        summary = format_probe_summary(0x05, packets)
        assert "CMD 0x05" in summary
        assert "2 packet" in summary
        # Hex head should be the first PROBE_HEX_PREVIEW_BYTES of the first
        # payload (bytes 0..31 = 00..1f).
        assert "000102" in summary

    def test_format_summary_zero_packets(self) -> None:
        summary = format_probe_summary(0x05, [])
        assert "0 packets" in summary
        assert "no response" in summary

    def test_output_dir_strips_report_id_prefix(self, tmp_path: Path) -> None:
        # Each packet has the hidapi 0x00 prefix as the first byte; the file
        # should contain only the 64-byte payloads concatenated.
        packets = [[0, *list(range(64))], [0, *([0xAA] * 64)]]
        write_probe_response(tmp_path, 0x05, packets)
        contents = (tmp_path / "cmd_05.bin").read_bytes()
        assert len(contents) == 128
        assert contents[:64] == bytes(range(64))
        assert contents[64:] == b"\xaa" * 64


class TestProbeCounts:
    """Per-CMD packet count: probe_one sends count=PROBE_COUNTS[cmd] in the
    request packet AND asks read_data for that many packets back."""

    @patch("ak820ctl.cli.open_device")
    @patch("ak820ctl.cli.session_end")
    @patch("ak820ctl.cli.read_data")
    @patch("ak820ctl.cli.send_report")
    def test_known_cmd_uses_documented_count(
        self,
        mock_send: MagicMock,
        mock_read: MagicMock,
        _mock_end: MagicMock,
        mock_open: MagicMock,
    ) -> None:
        dev = HidDeviceMock()
        mock_open.return_value = as_hid_device(dev)
        mock_read.return_value = []
        # CMD 0x15 (read_keymap) is documented as NUM_KEYMAP_CHUNKS (49).
        _ = probe_one(0x15)
        sent_packet = mock_send.call_args.args[1]
        # send_report is called with (device, packet_bytes); packet[8] holds count
        # because make_packet fills positions 0..8 from the 9 positional args
        # (REPORT_ID, cmd_byte, 6x 0x00, count).
        assert sent_packet[8] == PROBE_COUNTS[0x15]
        # read_data called with count=49 too.
        assert mock_read.call_args.kwargs["count"] == PROBE_COUNTS[0x15]

    @patch("ak820ctl.cli.open_device")
    @patch("ak820ctl.cli.session_end")
    @patch("ak820ctl.cli.read_data")
    @patch("ak820ctl.cli.send_report")
    def test_unknown_cmd_defaults_to_one(
        self,
        mock_send: MagicMock,
        mock_read: MagicMock,
        _mock_end: MagicMock,
        mock_open: MagicMock,
    ) -> None:
        dev = HidDeviceMock()
        mock_open.return_value = as_hid_device(dev)
        mock_read.return_value = []
        # 0x10 / 0x16 / 0x26 / 0xE0 aren't in PROBE_COUNTS, default to 1.
        _ = probe_one(0x10)
        sent_packet = mock_send.call_args.args[1]
        assert sent_packet[8] == PROBE_DEFAULT_COUNT == 1
        assert mock_read.call_args.kwargs["count"] == PROBE_DEFAULT_COUNT
