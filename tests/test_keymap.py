"""Tests for keymap readback (CMD 0x15)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

from hypothesis import given
from hypothesis import strategies as st
from typer.testing import CliRunner

from ak820ctl.cli import app
from ak820ctl.commands import CMD_READ_KEYMAP
from ak820ctl.keymap import KEYMAP_BYTES, NUM_KEYMAP_CHUNKS, parse_keymap_data, read_keymap
from tests.conftest import HidDeviceMock, ack_packet, as_hid_device, keymap_response_packets

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


# ── parse_keymap_data ────────────────────────────────────────────────────────


class TestParseKeymapData:
    def test_full_response_roundtrips(self) -> None:
        payload = bytes(range(256)) * (KEYMAP_BYTES // 256) + bytes(range(KEYMAP_BYTES % 256))
        packets = keymap_response_packets(payload)
        parsed = parse_keymap_data(packets)
        assert parsed == payload

    def test_truncated_response_pads_with_zero(self) -> None:
        # Only 5 chunks (320 bytes) come back. parse should pad to KEYMAP_BYTES.
        payload = bytes(range(256)) + bytes(range(64))
        packets = keymap_response_packets(payload)[:5]
        parsed = parse_keymap_data(packets)
        assert len(parsed) == KEYMAP_BYTES
        assert parsed[:320] == payload
        assert parsed[320:] == b"\x00" * (KEYMAP_BYTES - 320)

    def test_extra_packets_are_ignored(self) -> None:
        # 60 packets in (extra 11 beyond NUM_KEYMAP_CHUNKS). parse should
        # decode the first 49 and drop the rest.
        payload = b"\xab" * KEYMAP_BYTES
        packets = keymap_response_packets(payload)
        extra = [[0x00, *([0xCC] * 64)] for _ in range(11)]
        parsed = parse_keymap_data([*packets, *extra])
        assert parsed == payload

    def test_strips_hidapi_report_id_byte(self) -> None:
        # Each input packet is 65 bytes (1 ID prefix + 64 payload); the parser
        # must strip the prefix, not consume it as data.
        packets = [[0x99] + [i % 256 for i in range(64)] for _ in range(NUM_KEYMAP_CHUNKS)]
        parsed = parse_keymap_data(packets)
        # First parsed byte is index 0 of the first chunk's payload, not 0x99.
        assert parsed[0] == 0
        # And the 0x99 prefix never appears in the parsed output.
        assert 0x99 not in set(parsed)


# ── read_keymap ──────────────────────────────────────────────────────────────


class TestReadKeymap:
    @patch("ak820ctl.keymap.session_end")
    @patch("ak820ctl.keymap.session_save")
    @patch("ak820ctl.keymap.session_start")
    def test_returns_parsed_bytes(
        self,
        mock_start: MagicMock,
        _mock_save: MagicMock,
        _mock_end: MagicMock,
    ) -> None:
        """Mock the device's get_feature_report to play back a canned 49-packet
        response; verify read_keymap returns the expected bytes and that
        session_start was called once (matches read_perkey_stored semantics)."""
        dev = HidDeviceMock()
        payload = bytes((i * 7 + 3) & 0xFF for i in range(KEYMAP_BYTES))
        dev.get_feature_report.side_effect = [
            ack_packet(CMD_READ_KEYMAP),  # drained by read_data classifier
            *keymap_response_packets(payload),
        ]
        parsed = read_keymap(device=as_hid_device(dev))
        assert parsed == payload
        mock_start.assert_called_once_with(as_hid_device(dev))

    @patch("ak820ctl.keymap.session_end")
    @patch("ak820ctl.keymap.session_save")
    @patch("ak820ctl.keymap.session_start")
    def test_does_not_close_provided_device(
        self,
        _mock_start: MagicMock,
        _mock_save: MagicMock,
        _mock_end: MagicMock,
    ) -> None:
        dev = HidDeviceMock()
        _ = read_keymap(device=as_hid_device(dev))
        dev.close.assert_not_called()

    @patch("ak820ctl.keymap.session_end")
    @patch("ak820ctl.keymap.session_save")
    @patch("ak820ctl.keymap.session_start")
    @patch("ak820ctl.keymap.open_device")
    def test_opens_and_closes_device_when_not_provided(
        self,
        mock_open: MagicMock,
        _mock_start: MagicMock,
        _mock_save: MagicMock,
        _mock_end: MagicMock,
    ) -> None:
        dev = HidDeviceMock()
        mock_open.return_value = as_hid_device(dev)
        _ = read_keymap()
        mock_open.assert_called_once()
        dev.close.assert_called_once()


# ── Property: read -> parse roundtrip preserves arbitrary bytes ──────────────


@given(payload=st.binary(min_size=KEYMAP_BYTES, max_size=KEYMAP_BYTES))
def test_read_parse_roundtrip(payload: bytes) -> None:
    parsed = parse_keymap_data(keymap_response_packets(payload))
    assert parsed == payload


# ── CLI subcommand ──────────────────────────────────────────────────────────


class TestKeymapCli:
    def test_no_args_exits_1(self) -> None:
        result = runner.invoke(app, ["keymap"])
        assert result.exit_code == 1
        assert "No action selected" in result.output

    @patch("ak820ctl.cli.read_keymap")
    def test_dump_prints_json(self, mock_read: MagicMock) -> None:
        payload = bytes((i * 3) & 0xFF for i in range(KEYMAP_BYTES))
        mock_read.return_value = payload
        result = runner.invoke(app, ["keymap", "--dump"])
        assert result.exit_code == 0
        parsed = cast("dict[str, int | str]", json.loads(result.output))
        assert parsed["size"] == KEYMAP_BYTES
        assert parsed["hex"] == payload.hex()

    @patch("ak820ctl.cli.read_keymap")
    def test_save_writes_file(self, mock_read: MagicMock, tmp_path: Path) -> None:
        payload = b"\x42" * KEYMAP_BYTES
        mock_read.return_value = payload
        out = tmp_path / "km.json"
        result = runner.invoke(app, ["keymap", "--save", str(out)])
        assert result.exit_code == 0
        parsed = cast("dict[str, int | str]", json.loads(out.read_text(encoding="utf-8")))
        assert parsed["size"] == KEYMAP_BYTES
        assert parsed["hex"] == payload.hex()

    @patch("ak820ctl.cli.read_keymap")
    def test_save_dash_writes_to_stdout(self, mock_read: MagicMock) -> None:
        payload = b"\x01" * KEYMAP_BYTES
        mock_read.return_value = payload
        result = runner.invoke(app, ["keymap", "--save", "-"])
        assert result.exit_code == 0
        parsed = cast("dict[str, int | str]", json.loads(result.output))
        assert parsed["hex"] == payload.hex()

    @patch("ak820ctl.cli.read_keymap", side_effect=RuntimeError("no device"))
    def test_runtime_error_exits_1(self, _mock_read: MagicMock) -> None:
        result = runner.invoke(app, ["keymap", "--dump"])
        assert result.exit_code == 1
        assert "no device" in result.output
