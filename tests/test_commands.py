"""Tests for command packet construction."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from ak820ctl.commands import (
    DIRECTION_NAMES,
    DIRECTIONS,
    LIGHT_MODE_NAMES,
    LIGHT_MODES,
    SLEEP_VALUES,
    get_device_info,
    get_firmware_version,
    read_lighting,
    sync_time,
)
from ak820ctl.hid import REPORT_ID


def test_light_modes_complete() -> None:
    assert "off" in LIGHT_MODES
    assert "static" in LIGHT_MODES
    assert "breath" in LIGHT_MODES
    assert "spectrum" in LIGHT_MODES
    assert "custom" in LIGHT_MODES
    assert LIGHT_MODES["off"] == 0x00
    assert LIGHT_MODES["custom"] == 0x80


def test_directions() -> None:
    assert DIRECTIONS == {"left": 0, "down": 1, "up": 2, "right": 3}


def test_sleep_values() -> None:
    assert SLEEP_VALUES == {"never": 0, "1min": 1, "5min": 2, "30min": 3}


def test_sync_time_packet_structure() -> None:
    """Verify the exact byte layout of the time sync packets."""
    mock_device = MagicMock()
    mock_device.get_feature_report.return_value = [0] * 65

    dt = datetime(2025, 3, 15, 14, 30, 45)

    with patch("ak820ctl.commands.open_device", return_value=mock_device):
        result = sync_time(device=mock_device, dt=dt)

    assert result == dt

    # Verify send_feature_report was called 4 times (start, preamble, data, save)
    calls = mock_device.send_feature_report.call_args_list
    assert len(calls) == 4

    # Step 1: CMD_START — report bytes start with 0x00 (report ID prefix) + 0x04 0x18
    start_data = bytes(calls[0].args[0])
    assert start_data[0] == 0x00  # hidapi report ID prefix
    assert start_data[1] == REPORT_ID
    assert start_data[2] == 0x18

    # Step 2: CMD_TIME preamble — 0x04 0x28
    preamble_data = bytes(calls[1].args[0])
    assert preamble_data[1] == REPORT_ID
    assert preamble_data[2] == 0x28

    # Step 3: Time data packet
    time_data = bytes(calls[2].args[0])
    assert time_data[1] == 0x00  # report ID = 0x00 for data
    assert time_data[2] == 0x01  # slot
    assert time_data[3] == 0x5A  # magic
    assert time_data[4] == 25  # 2025 - 2000
    assert time_data[5] == 3  # March
    assert time_data[6] == 15  # day
    assert time_data[7] == 14  # hour
    assert time_data[8] == 30  # minute
    assert time_data[9] == 45  # second
    assert time_data[11] == 0x04  # fixed constant
    assert time_data[63] == 0xAA  # delimiter
    assert time_data[64] == 0x55  # delimiter

    # Step 4: CMD_SAVE — 0x04 0x02
    save_data = bytes(calls[3].args[0])
    assert save_data[1] == REPORT_ID
    assert save_data[2] == 0x02

    # Verify device was closed (own_device=False since we passed it)
    mock_device.close.assert_not_called()


def test_sync_time_closes_device_when_created() -> None:
    """Device opened internally should be closed after sync."""
    mock_device = MagicMock()
    mock_device.get_feature_report.return_value = [0] * 65

    with patch("ak820ctl.commands.open_device", return_value=mock_device):
        sync_time(dt=datetime(2025, 1, 1, 0, 0, 0))

    mock_device.close.assert_called_once()


def test_reverse_lookup_tables() -> None:
    """LIGHT_MODE_NAMES and DIRECTION_NAMES are correct inverses."""
    for name, val in LIGHT_MODES.items():
        assert LIGHT_MODE_NAMES[val] == name
    for name, val in DIRECTIONS.items():
        assert DIRECTION_NAMES[val] == name


def test_get_device_info_parses_response() -> None:
    """CMD 0x05 response parsed with correct LE byte offsets."""
    mock_device = MagicMock()
    # Simulate: send_report does one send, read_data discards ACK then reads data
    # ACK echo, then real data (hidapi report ID 0x00 at index 0)
    ack = [0x00, 0x04, 0x05] + [0x00] * 62
    data = [0x00] * 65
    data[1] = 0x40  # capabilities lo
    data[2] = 0x30  # capabilities hi
    data[5] = 0x45  # VID lo
    data[6] = 0x0C  # VID hi
    data[7] = 0x09  # PID lo
    data[8] = 0x80  # PID hi
    data[9] = 0x14  # FW lo (minor=20)
    data[10] = 0x01  # FW hi (major=1)
    data[11] = 0xFF
    data[12] = 0xFF
    mock_device.get_feature_report.side_effect = [ack, data]

    with patch("ak820ctl.commands.open_device", return_value=mock_device):
        info = get_device_info(device=mock_device)

    assert info.vid == 0x0C45
    assert info.pid == 0x8009
    assert info.firmware == "1.20"
    assert info.capabilities == 0x3040
    mock_device.close.assert_not_called()


def test_get_device_info_opens_and_closes_device() -> None:
    mock_device = MagicMock()
    ack = [0x00] * 65
    data = [0x00] * 65
    mock_device.get_feature_report.side_effect = [ack, data]

    with patch("ak820ctl.commands.open_device", return_value=mock_device):
        get_device_info()

    mock_device.close.assert_called_once()


def test_get_device_info_no_data() -> None:
    """Returns unknown firmware when no packets received."""
    mock_device = MagicMock()
    mock_device.get_feature_report.side_effect = OSError("no device")

    with patch("ak820ctl.commands.open_device", return_value=mock_device):
        info = get_device_info(device=mock_device)

    assert info.firmware == "unknown"


def test_get_firmware_version_delegates() -> None:
    mock_device = MagicMock()
    ack = [0x00] * 65
    data = [0x00] * 65
    data[9] = 0x14
    data[10] = 0x01
    mock_device.get_feature_report.side_effect = [ack, data]

    with patch("ak820ctl.commands.open_device", return_value=mock_device):
        ver = get_firmware_version(device=mock_device)

    assert ver == "1.20"


def test_read_lighting_parses_response() -> None:
    """CMD 0x12 response parsed with correct +1 hidapi offset."""
    mock_device = MagicMock()
    ack = [0x00, 0x04, 0x12] + [0x00] * 62
    data = [0x00] * 65
    # hidapi byte 0 = report ID, data starts at byte 1
    data[1] = 0x01  # mode: static
    data[2] = 0xFF  # R
    data[3] = 0x00  # G
    data[4] = 0x80  # B
    data[9] = 0x01  # rainbow: on
    data[10] = 0x04  # brightness
    data[11] = 0x02  # speed
    data[12] = 0x03  # direction: right
    mock_device.get_feature_report.side_effect = [ack, data]

    with patch("ak820ctl.commands.open_device", return_value=mock_device):
        cfg = read_lighting(device=mock_device)

    assert cfg.mode == "static"
    assert cfg.mode_value == 0x01
    assert cfg.r == 0xFF
    assert cfg.g == 0x00
    assert cfg.b == 0x80
    assert cfg.rainbow is True
    assert cfg.brightness == 4
    assert cfg.speed == 2
    assert cfg.direction == "right"


def test_read_lighting_unknown_mode() -> None:
    mock_device = MagicMock()
    ack = [0x00] * 65
    data = [0x00] * 65
    data[1] = 0xFE  # unknown mode
    mock_device.get_feature_report.side_effect = [ack, data]

    with patch("ak820ctl.commands.open_device", return_value=mock_device):
        cfg = read_lighting(device=mock_device)

    assert cfg.mode == "0xfe"


def test_read_lighting_no_data() -> None:
    mock_device = MagicMock()
    mock_device.get_feature_report.side_effect = OSError("no device")

    with patch("ak820ctl.commands.open_device", return_value=mock_device):
        cfg = read_lighting(device=mock_device)

    assert cfg.mode == "off"  # default LightingConfig
