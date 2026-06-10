"""Tests for HID packet construction and device probing."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ak820ctl.hid import (
    DISPLAY_INTERFACE,
    DISPLAY_USAGE_PAGE,
    INTERFACE,
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
from tests.conftest import HidDeviceMock, as_hid_device


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
    p1 = [0x00, 0x11] + [0] * 63
    p2 = [0x00, 0x22] + [0] * 63
    # First call is the ACK discard, then 2 successful reads, then OSError.
    mock_dev.get_feature_report.side_effect = [
        [0] * 65,  # ACK
        p1,
        p2,
        OSError("read failed"),
    ]
    packets = read_data(as_hid_device(mock_dev), count=5)
    assert len(packets) == 2
    assert packets[0][1] == 0x11
    assert packets[1][1] == 0x22


def test_read_data_handles_ack_oserror() -> None:
    """OSError on the ACK discard is logged and ignored; data reads proceed."""
    mock_dev = HidDeviceMock()
    mock_dev.get_feature_report.side_effect = [
        OSError("ack failed"),
        [0x00, 0x42] + [0] * 63,
    ]
    packets = read_data(as_hid_device(mock_dev), count=1)
    assert len(packets) == 1
    assert packets[0][1] == 0x42
