"""Tests for dump and restore functionality."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 — used at runtime (tmp_path fixture)
from unittest.mock import patch

from ak820ctl.commands import dump_settings, restore_settings
from ak820ctl.models import DeviceInfo, KeyboardDump, LightingConfig
from tests.conftest import HidDeviceMock, as_hid_device


def _mock_device() -> HidDeviceMock:
    """Create a mock device that returns valid ID and lighting responses."""
    dev = HidDeviceMock()
    id_ack = [0x00, 0x04, 0x05] + [0x00] * 62
    id_data = [0x00] * 65
    id_data[1] = 0x40
    id_data[2] = 0x30
    id_data[5] = 0x45
    id_data[6] = 0x0C
    id_data[7] = 0x09
    id_data[8] = 0x80
    id_data[9] = 0x14
    id_data[10] = 0x01
    id_data[11] = 0xFF
    id_data[12] = 0xFF

    light_ack = [0x00, 0x04, 0x12] + [0x00] * 62
    light_data = [0x00] * 65
    light_data[1] = 0x01  # static
    light_data[2] = 0xFF  # R
    light_data[3] = 0x00  # G
    light_data[4] = 0x00  # B
    light_data[10] = 0x05  # brightness
    light_data[11] = 0x03  # speed

    dev.get_feature_report.side_effect = [id_ack, id_data, light_ack, light_data]
    return dev


def test_dump_settings() -> None:
    dev = _mock_device()
    data = dump_settings(device=as_hid_device(dev))

    assert isinstance(data, KeyboardDump)
    assert data.device.firmware == "1.20"
    assert data.device.vid == 0x0C45
    assert data.lighting.mode == "static"
    assert data.lighting.r == 0xFF


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    dump = KeyboardDump(
        device=DeviceInfo(vid=0x0C45, pid=0x8009, firmware="1.20"),
        lighting=LightingConfig(
            mode="breath",
            r=0,
            g=255,
            b=0,
            brightness=3,
            speed=2,
            direction="up",
        ),
    )
    path = tmp_path / "settings.json"
    dump.save(path)

    assert path.exists()
    loaded = KeyboardDump.load(path)
    assert loaded == dump


def test_save_produces_valid_json(tmp_path: Path) -> None:
    dump = KeyboardDump(lighting=LightingConfig(mode="off"))
    path = tmp_path / "test.json"
    dump.save(path)

    loaded = KeyboardDump.load(path)
    assert loaded.lighting.mode == "off"


def test_restore_applies_lighting() -> None:
    dev = HidDeviceMock()
    dev.get_feature_report.return_value = [0x00] * 65

    dump = KeyboardDump(
        lighting=LightingConfig(
            mode="breath",
            r=128,
            g=64,
            b=32,
            brightness=3,
            speed=2,
            direction="up",
            rainbow=True,
        ),
    )

    actions = restore_settings(dump, device=as_hid_device(dev), skip_time=True)

    assert "lighting: breath" in actions
    assert dev.send_feature_report.call_count >= 3


def test_restore_syncs_time() -> None:
    dev = HidDeviceMock()
    dev.get_feature_report.return_value = [0x00] * 65

    dump = KeyboardDump(lighting=LightingConfig(mode="static"))

    actions = restore_settings(dump, device=as_hid_device(dev), skip_time=False)

    assert "time: synced" in actions


def test_restore_skip_time() -> None:
    dev = HidDeviceMock()
    dev.get_feature_report.return_value = [0x00] * 65

    dump = KeyboardDump(lighting=LightingConfig(mode="off"))

    actions = restore_settings(dump, device=as_hid_device(dev), skip_time=True)

    assert "time: synced" not in actions


def test_restore_closes_device_when_created() -> None:
    dev = HidDeviceMock()
    dev.get_feature_report.return_value = [0x00] * 65

    dump = KeyboardDump()

    with patch("ak820ctl.commands.open_device", return_value=as_hid_device(dev)):
        _ = restore_settings(dump, skip_time=True)

    dev.close.assert_called_once()


def test_model_defaults() -> None:
    dump = KeyboardDump()
    assert dump.device.firmware == "unknown"
    assert dump.lighting.mode == "off"
    assert dump.lighting.brightness == 5
