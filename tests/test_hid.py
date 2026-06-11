"""Tests for HID packet construction and device probing."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ak820ctl.hid import (
    DISPLAY_INTERFACE,
    DISPLAY_USAGE_PAGE,
    INTERFACE,
    MAX_ACK_DRAINS,
    PACKET_SIZE,
    PID,
    REPORT_ID,
    VID,
    find_device,
    find_display_device,
    make_packet,
    open_device,
    open_display_device,
    read_data,
    send_command,
)
from tests.conftest import HidDeviceMock, ack_packet, as_hid_device


def test_make_packet_default_size() -> None:
    pkt = make_packet(0x04, 0x18)
    assert len(pkt) == PACKET_SIZE
    assert pkt[0] == 0x04
    assert pkt[1] == 0x18
    assert all(b == 0 for b in pkt[2:])


def test_make_packet_custom_size() -> None:
    pkt = make_packet(0xFF, size=8)
    assert len(pkt) == 8
    assert pkt[0] == 0xFF
    assert all(b == 0 for b in pkt[1:])


def test_make_packet_multiple_bytes() -> None:
    pkt = make_packet(0x04, 0x28, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01)
    assert pkt[0] == REPORT_ID
    assert pkt[1] == 0x28
    assert pkt[8] == 0x01


def test_report_id_constant() -> None:
    assert REPORT_ID == 0x04


def test_packet_size_constant() -> None:
    assert PACKET_SIZE == 64


# ── find_device / open_device ────────────────────────────────────────────────


def _enum_dict(
    *,
    interface_number: int = 3,
    usage_page: int = 0,
    path: bytes = b"/dev/hidraw3",
) -> dict[str, object]:
    """Build a minimal hidapi enumerate() dict for the bits we read."""
    return {
        "interface_number": interface_number,
        "usage_page": usage_page,
        "path": path,
        "vendor_id": VID,
        "product_id": PID,
    }


def test_find_device_returns_interface_3_path() -> None:
    enums = [
        _enum_dict(interface_number=0, path=b"/dev/hidraw0"),
        _enum_dict(interface_number=INTERFACE, path=b"/dev/hidraw3"),
    ]
    with patch("ak820ctl.hid.hid.enumerate", return_value=enums):
        path = find_device()
    assert path == b"/dev/hidraw3"


def test_find_device_raises_when_not_connected() -> None:
    with (
        patch("ak820ctl.hid.hid.enumerate", return_value=[]),
        pytest.raises(RuntimeError, match="not found"),
    ):
        _ = find_device()


def test_open_device_calls_open_path() -> None:
    mock_dev = HidDeviceMock()
    with (
        patch("ak820ctl.hid.find_device", return_value=b"/dev/hidraw3"),
        patch("ak820ctl.hid.hid.device", return_value=as_hid_device(mock_dev)),
    ):
        d = open_device()
    mock_dev.open_path.assert_called_once_with(b"/dev/hidraw3")
    assert d is as_hid_device(mock_dev)


def test_open_device_with_explicit_path_skips_find() -> None:
    mock_dev = HidDeviceMock()
    with (
        patch("ak820ctl.hid.find_device") as mock_find,
        patch("ak820ctl.hid.hid.device", return_value=as_hid_device(mock_dev)),
    ):
        _ = open_device(path=b"/dev/hidraw7")
    mock_find.assert_not_called()
    mock_dev.open_path.assert_called_once_with(b"/dev/hidraw7")


# ── find_display_device / open_display_device ────────────────────────────────


def test_find_display_device_prefers_usage_page() -> None:
    enums = [
        _enum_dict(interface_number=DISPLAY_INTERFACE, path=b"/dev/by-iface"),
        _enum_dict(usage_page=DISPLAY_USAGE_PAGE, path=b"/dev/by-usage-page"),
    ]
    with patch("ak820ctl.hid.hid.enumerate", return_value=enums):
        path = find_display_device()
    # Usage page is matched first
    assert path == b"/dev/by-usage-page"


def test_find_display_device_falls_back_to_interface_number() -> None:
    """When no entry exposes usage_page, fall back to interface_number."""
    enums = [
        _enum_dict(interface_number=0, path=b"/dev/hidraw0"),
        _enum_dict(interface_number=DISPLAY_INTERFACE, path=b"/dev/hidraw2"),
    ]
    with patch("ak820ctl.hid.hid.enumerate", return_value=enums):
        path = find_display_device()
    assert path == b"/dev/hidraw2"


def test_find_display_device_raises_when_neither_matches() -> None:
    enums = [_enum_dict(interface_number=0, path=b"/dev/hidraw0")]
    with (
        patch("ak820ctl.hid.hid.enumerate", return_value=enums),
        pytest.raises(RuntimeError, match="display interface not found"),
    ):
        _ = find_display_device()


def test_open_display_device_calls_open_path() -> None:
    mock_dev = HidDeviceMock()
    with (
        patch("ak820ctl.hid.find_display_device", return_value=b"/dev/hidraw2"),
        patch("ak820ctl.hid.hid.device", return_value=as_hid_device(mock_dev)),
    ):
        _ = open_display_device()
    mock_dev.open_path.assert_called_once_with(b"/dev/hidraw2")


# ── send_command / read_data error swallowing ────────────────────────────────


def test_send_command_swallows_oserror_on_get_feature_report() -> None:
    """STALL on the GET_REPORT handshake is logged and silently swallowed."""
    mock_dev = HidDeviceMock()
    mock_dev.get_feature_report.side_effect = OSError("STALL")
    # Should NOT raise even though get_feature_report blows up.
    send_command(as_hid_device(mock_dev), make_packet(REPORT_ID, 0x18))
    mock_dev.send_feature_report.assert_called_once()
    mock_dev.get_feature_report.assert_called_once_with(0x00, 65)


def test_read_data_returns_packets_until_oserror() -> None:
    """Stops the read loop on OSError, returning what was collected so far."""
    mock_dev = HidDeviceMock()
    cmd = 0x05
    p1 = [0x00, 0x11] + [0] * 63
    p2 = [0x00, 0x22] + [0] * 63
    # ACK echo first (drained by the classifier), then 2 data packets, then OSError.
    mock_dev.get_feature_report.side_effect = [
        ack_packet(cmd),
        p1,
        p2,
        OSError("read failed"),
    ]
    packets = read_data(as_hid_device(mock_dev), cmd, count=5)
    assert len(packets) == 2
    assert packets[0][1] == 0x11
    assert packets[1][1] == 0x22


def test_read_data_handles_first_read_oserror() -> None:
    """OSError on the very first read aborts and returns an empty list."""
    mock_dev = HidDeviceMock()
    mock_dev.get_feature_report.side_effect = OSError("read failed")
    packets = read_data(as_hid_device(mock_dev), 0x05, count=1)
    assert packets == []


def test_read_data_data_first_is_treated_as_data() -> None:
    """When the queue has no leading ACK echo (data-first ordering), the
    first packet is data, not silently discarded as ACK like the old code did.

    This is the core of the ACK-classification fix: previously the first
    GET_REPORT was always treated as ACK by position, so any data-first
    response was eaten and the next read returned stale/wrong bytes.
    """
    mock_dev = HidDeviceMock()
    data = [0x00, 0x40, 0x30] + [0] * 62
    mock_dev.get_feature_report.return_value = data
    packets = read_data(as_hid_device(mock_dev), 0x05, count=1)
    assert len(packets) == 1
    assert packets[0] == data
    # Only one GET_REPORT was needed — no extra ACK drain.
    assert mock_dev.get_feature_report.call_count == 1


def test_read_data_drains_stale_ack_echoes_before_data() -> None:
    """Multiple ACK echoes for our cmd_byte sitting on the queue are drained
    until the real data packet appears."""
    mock_dev = HidDeviceMock()
    cmd = 0x12
    data = [0x00, 0x01, 0xAA, 0xBB, 0xCC] + [0] * 60
    mock_dev.get_feature_report.side_effect = [
        ack_packet(cmd),  # stale echo from a prior read
        ack_packet(cmd),  # stale echo from a prior read
        data,
    ]
    packets = read_data(as_hid_device(mock_dev), cmd, count=1)
    assert len(packets) == 1
    assert packets[0] == data
    assert mock_dev.get_feature_report.call_count == 3


def test_read_data_does_not_drain_other_cmd_echoes() -> None:
    """An ACK echo carrying a *different* cmd_byte is NOT treated as our
    echo — it's a data packet from someone else's perspective and we
    return it as-is. Prevents over-draining when the queue holds residue
    from another command path."""
    mock_dev = HidDeviceMock()
    other_echo = ack_packet(0x99)
    mock_dev.get_feature_report.return_value = other_echo
    packets = read_data(as_hid_device(mock_dev), 0x05, count=1)
    assert packets == [other_echo]


def test_read_data_drain_safety_bound() -> None:
    """If the firmware is stuck emitting ACK echoes forever, read_data
    bails out after MAX_ACK_DRAINS rather than looping unbounded."""
    mock_dev = HidDeviceMock()
    cmd = 0x05
    mock_dev.get_feature_report.return_value = ack_packet(cmd)
    packets = read_data(as_hid_device(mock_dev), cmd, count=1)
    assert packets == []
    # Bounded — we shouldn't have made more than MAX_ACK_DRAINS+1 calls.
    assert mock_dev.get_feature_report.call_count <= MAX_ACK_DRAINS + 1


def test_read_data_collects_multiple_data_packets() -> None:
    """count > 1: classifier collects exactly `count` data packets, ignoring
    any leading ACK echo."""
    mock_dev = HidDeviceMock()
    cmd = 0xF5
    d0 = [0x00, 0x00, 0xAA] + [0] * 62
    d1 = [0x00, 0x10, 0xBB] + [0] * 62
    d2 = [0x00, 0x20, 0xCC] + [0] * 62
    mock_dev.get_feature_report.side_effect = [ack_packet(cmd), d0, d1, d2]
    packets = read_data(as_hid_device(mock_dev), cmd, count=3)
    assert packets == [d0, d1, d2]
