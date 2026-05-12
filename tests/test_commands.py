"""Tests for command packet construction."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from ak820ctl.commands import (
    DIRECTIONS,
    LIGHT_MODES,
    SLEEP_VALUES,
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
