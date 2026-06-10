"""Tests for command packet construction."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from unittest.mock import patch

import pytest

from ak820ctl.commands import (
    DIRECTION_NAMES,
    DIRECTIONS,
    LIGHT_MODE_NAMES,
    LIGHT_MODES,
    SLEEP_VALUES,
    dump_settings,
    get_device_info,
    get_firmware_version,
    read_lighting,
    restore_settings,
    set_lighting,
    set_sleep,
    sync_time,
)
from ak820ctl.hid import REPORT_ID
from ak820ctl.models import DeviceInfo, KeyboardDump, LightingConfig
from tests.conftest import HidDeviceMock, ack_packet, as_hid_device, device_info_packet


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
    mock_device = HidDeviceMock()
    mock_device.get_feature_report.return_value = [0] * 65

    dt = datetime(2025, 3, 15, 14, 30, 45)

    with patch("ak820ctl.commands.open_device", return_value=as_hid_device(mock_device)):
        result = sync_time(device=as_hid_device(mock_device), dt=dt)

    assert result == dt

    # Verify send_feature_report was called 4 times (start, preamble, data, save)
    calls = mock_device.send_feature_report.call_args_list
    assert len(calls) == 4

    # Step 1: CMD_START — report bytes start with 0x00 (report ID prefix) + 0x04 0x18
    start_data = bytes(cast("bytes | list[int]", calls[0].args[0]))
    assert start_data[0] == 0x00  # hidapi report ID prefix
    assert start_data[1] == REPORT_ID
    assert start_data[2] == 0x18

    # Step 2: CMD_TIME preamble — 0x04 0x28
    preamble_data = bytes(cast("bytes | list[int]", calls[1].args[0]))
    assert preamble_data[1] == REPORT_ID
    assert preamble_data[2] == 0x28

    # Step 3: Time data packet
    time_data = bytes(cast("bytes | list[int]", calls[2].args[0]))
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
    save_data = bytes(cast("bytes | list[int]", calls[3].args[0]))
    assert save_data[1] == REPORT_ID
    assert save_data[2] == 0x02

    # Verify device was closed (own_device=False since we passed it)
    mock_device.close.assert_not_called()


def test_sync_time_closes_device_when_created() -> None:
    """Device opened internally should be closed after sync."""
    mock_device = HidDeviceMock()
    mock_device.get_feature_report.return_value = [0] * 65

    with patch("ak820ctl.commands.open_device", return_value=as_hid_device(mock_device)):
        _ = sync_time(dt=datetime(2025, 1, 1, 0, 0, 0))

    mock_device.close.assert_called_once()


def test_reverse_lookup_tables() -> None:
    """LIGHT_MODE_NAMES and DIRECTION_NAMES are correct inverses."""
    for name, val in LIGHT_MODES.items():
        assert LIGHT_MODE_NAMES[val] == name
    for name, val in DIRECTIONS.items():
        assert DIRECTION_NAMES[val] == name


def test_get_device_info_parses_response() -> None:
    """CMD 0x05 response parsed with correct LE byte offsets."""
    mock_device = HidDeviceMock()
    # send_report does one send, read_data discards ACK then reads data.
    mock_device.get_feature_report.side_effect = [
        ack_packet(0x05),
        device_info_packet(vid=0x0C45, pid=0x8009, fw_major=1, fw_minor=20, capabilities=0x3040),
    ]

    with patch("ak820ctl.commands.open_device", return_value=as_hid_device(mock_device)):
        info = get_device_info(device=as_hid_device(mock_device))

    assert info.vid == 0x0C45
    assert info.pid == 0x8009
    assert info.firmware == "1.20"
    assert info.capabilities == 0x3040
    mock_device.close.assert_not_called()


def test_get_device_info_opens_and_closes_device() -> None:
    mock_device = HidDeviceMock()
    mock_device.get_feature_report.side_effect = [ack_packet(0x05), device_info_packet()]

    with patch("ak820ctl.commands.open_device", return_value=as_hid_device(mock_device)):
        _ = get_device_info()

    mock_device.close.assert_called_once()


def test_get_device_info_no_data() -> None:
    """Returns unknown firmware when no packets received."""
    mock_device = HidDeviceMock()
    mock_device.get_feature_report.side_effect = OSError("no device")

    with patch("ak820ctl.commands.open_device", return_value=as_hid_device(mock_device)):
        info = get_device_info(device=as_hid_device(mock_device))

    assert info.firmware == "unknown"


def test_get_firmware_version_delegates() -> None:
    mock_device = HidDeviceMock()
    mock_device.get_feature_report.side_effect = [
        ack_packet(0x05),
        device_info_packet(fw_major=1, fw_minor=20),
    ]

    with patch("ak820ctl.commands.open_device", return_value=as_hid_device(mock_device)):
        ver = get_firmware_version(device=as_hid_device(mock_device))

    assert ver == "1.20"


def test_read_lighting_parses_response() -> None:
    """CMD 0x12 response parsed with correct +1 hidapi offset."""
    mock_device = HidDeviceMock()
    ack = ack_packet(0x12)
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

    with patch("ak820ctl.commands.open_device", return_value=as_hid_device(mock_device)):
        cfg = read_lighting(device=as_hid_device(mock_device))

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
    mock_device = HidDeviceMock()
    data = [0x00] * 65
    data[1] = 0xFE  # unknown mode
    mock_device.get_feature_report.side_effect = [ack_packet(0x12), data]

    with patch("ak820ctl.commands.open_device", return_value=as_hid_device(mock_device)):
        cfg = read_lighting(device=as_hid_device(mock_device))

    assert cfg.mode == "0xfe"


def test_read_lighting_no_data() -> None:
    mock_device = HidDeviceMock()
    mock_device.get_feature_report.side_effect = OSError("no device")

    with patch("ak820ctl.commands.open_device", return_value=as_hid_device(mock_device)):
        cfg = read_lighting(device=as_hid_device(mock_device))

    assert cfg.mode == "off"  # default LightingConfig


# ── set_lighting ──────────────────────────────────────────────────────────────


def test_set_lighting_unknown_mode_raises() -> None:
    with pytest.raises(ValueError, match="Unknown mode 'bogus'"):
        set_lighting(mode="bogus")


def test_set_lighting_succeeds() -> None:
    mock_device = HidDeviceMock()
    set_lighting(
        device=as_hid_device(mock_device),
        mode="breath",
        r=0xFF,
        g=0x80,
        b=0x40,
        brightness=4,
        speed=2,
        direction="up",
    )
    # 1 START + 2 send_command (preamble + data) + 1 SAVE = 4 sends
    assert mock_device.send_feature_report.call_count == 4
    mock_device.close.assert_not_called()


def test_set_lighting_opens_and_closes_device() -> None:
    mock_device = HidDeviceMock()
    with patch("ak820ctl.commands.open_device", return_value=as_hid_device(mock_device)):
        set_lighting(mode="static")
    mock_device.close.assert_called_once()


def test_set_lighting_unknown_direction_falls_back_to_left() -> None:
    """Unknown directions silently coerce to 'left' (value 0)."""
    mock_device = HidDeviceMock()
    set_lighting(device=as_hid_device(mock_device), mode="static", direction="diagonal")
    # The data packet is the 3rd send (after START and preamble). send_report
    # prefixes the buf with a 0x00 hidapi report ID, so the direction byte at
    # buf[11] (set_lighting layout) lands at index 12 on the wire.
    data_payload = bytes(
        cast("bytes | list[int]", mock_device.send_feature_report.call_args_list[2].args[0])
    )
    assert data_payload[12] == 0  # 'left' = 0


# ── set_sleep ─────────────────────────────────────────────────────────────────


def test_set_sleep_unknown_timeout_raises() -> None:
    with pytest.raises(ValueError, match="Unknown timeout 'forever'"):
        set_sleep(timeout="forever")


def test_set_sleep_succeeds() -> None:
    mock_device = HidDeviceMock()
    set_sleep(device=as_hid_device(mock_device), timeout="5min")
    # 1 START + 1 data + 1 SAVE = 3 sends
    assert mock_device.send_feature_report.call_count == 3
    mock_device.close.assert_not_called()


def test_set_sleep_opens_and_closes_device() -> None:
    mock_device = HidDeviceMock()
    with patch("ak820ctl.commands.open_device", return_value=as_hid_device(mock_device)):
        set_sleep(timeout="never")
    mock_device.close.assert_called_once()


# ── dump_settings / restore_settings ──────────────────────────────────────────


def _device_info_responder(mock_device: HidDeviceMock) -> None:
    """Wire mock_device.get_feature_report to satisfy both get_device_info and
    read_lighting (each does ack -> data)."""
    light_data = [0x00] * 65
    light_data[1] = 0x01  # static
    mock_device.get_feature_report.side_effect = [
        ack_packet(0x05),
        device_info_packet(vid=0x0C45, pid=0x8009, fw_major=1, fw_minor=20),
        ack_packet(0x12),
        light_data,
    ]


def test_dump_settings_opens_and_closes_device() -> None:
    mock_device = HidDeviceMock()
    _device_info_responder(mock_device)
    with patch("ak820ctl.commands.open_device", return_value=as_hid_device(mock_device)):
        dump = dump_settings()
    assert dump.device.firmware == "1.20"
    assert dump.lighting.mode == "static"
    mock_device.close.assert_called_once()


def test_restore_settings_returns_actions_lighting_and_time() -> None:
    mock_device = HidDeviceMock()
    dump = KeyboardDump(
        device=DeviceInfo(vid=0x0C45, pid=0x8009, firmware="1.20"),
        lighting=LightingConfig(mode="breath", r=0xFF, brightness=3),
    )
    actions = restore_settings(dump, device=as_hid_device(mock_device), skip_time=False)
    assert "lighting: breath" in actions
    assert "time: synced" in actions


def test_restore_settings_skip_time() -> None:
    mock_device = HidDeviceMock()
    dump = KeyboardDump(lighting=LightingConfig(mode="off"))
    actions = restore_settings(dump, device=as_hid_device(mock_device), skip_time=True)
    assert "time: synced" not in actions


def test_restore_settings_unknown_mode_falls_back_to_mode_value() -> None:
    """If cfg.mode is a string like '0x1f' (unknown), restore_settings should
    resolve via mode_value through LIGHT_MODE_NAMES."""
    mock_device = HidDeviceMock()
    # mode_value=0x01 is 'static'; cfg.mode 'mystery' is unknown, so we expect
    # restore_settings to use mode_value (0x01) -> 'static'.
    cfg = LightingConfig(mode="mystery", mode_value=0x01)
    dump = KeyboardDump(lighting=cfg)
    actions = restore_settings(dump, device=as_hid_device(mock_device), skip_time=True)
    assert "lighting: static" in actions


def test_restore_settings_opens_and_closes_device() -> None:
    mock_device = HidDeviceMock()
    dump = KeyboardDump(lighting=LightingConfig(mode="off"))
    with patch("ak820ctl.commands.open_device", return_value=as_hid_device(mock_device)):
        _ = restore_settings(dump, skip_time=True)
    mock_device.close.assert_called_once()
