"""High-level commands for the AK820 keyboard."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from ak820ctl.hid import (
    PACKET_SIZE,
    REPORT_ID,
    make_packet,
    open_device,
    send_command,
    session_save,
    session_start,
)

if TYPE_CHECKING:
    import hid


def sync_time(device: hid.device | None = None, dt: datetime | None = None) -> datetime:
    """Sync the keyboard clock to the given (or current local) time.

    Returns the datetime that was synced.
    """
    if dt is None:
        dt = datetime.now()

    own_device = device is None
    if device is None:
        device = open_device()

    try:
        # Step 1: START
        session_start(device)

        # Step 2: CMD_TIME preamble (0x28)
        preamble = make_packet(REPORT_ID, 0x28, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01)
        send_command(device, preamble)

        # Step 3: Time data packet (report ID = 0x00, not 0x04)
        year = dt.year - 2000
        buf = bytearray(PACKET_SIZE)
        buf[0] = 0x00
        buf[1] = 0x01
        buf[2] = 0x5A  # magic
        buf[3] = year
        buf[4] = dt.month
        buf[5] = dt.day
        buf[6] = dt.hour
        buf[7] = dt.minute
        buf[8] = dt.second
        buf[9] = 0x00
        buf[10] = 0x04  # fixed constant
        buf[62] = 0xAA  # delimiter
        buf[63] = 0x55
        send_command(device, bytes(buf))

        # Step 4: SAVE
        session_save(device)
    finally:
        if own_device:
            device.close()

    return dt


# Lighting mode names matching the firmware order
LIGHT_MODES = {
    "off": 0x00,
    "static": 0x01,
    "single-on": 0x02,
    "single-off": 0x03,
    "glittering": 0x04,
    "falling": 0x05,
    "colourful": 0x06,
    "breath": 0x07,
    "spectrum": 0x08,
    "outward": 0x09,
    "scrolling": 0x0A,
    "rolling": 0x0B,
    "rotating": 0x0C,
    "explode": 0x0D,
    "launch": 0x0E,
    "ripples": 0x0F,
    "flowing": 0x10,
    "pulsating": 0x11,
    "tilt": 0x12,
    "shuttle": 0x13,
    "custom": 0x80,
}

DIRECTIONS = {"left": 0, "down": 1, "up": 2, "right": 3}

SLEEP_VALUES = {"never": 0, "1min": 1, "5min": 2, "30min": 3}


def set_lighting(  # noqa: PLR0913
    device: hid.device | None = None,
    *,
    mode: str = "static",
    r: int = 255,
    g: int = 255,
    b: int = 255,
    rainbow: bool = False,
    brightness: int = 5,
    speed: int = 3,
    direction: str = "left",
) -> None:
    """Set the keyboard lighting mode."""
    mode_val = LIGHT_MODES.get(mode)
    if mode_val is None:
        msg = f"Unknown mode '{mode}'. Available: {', '.join(LIGHT_MODES)}"
        raise ValueError(msg)
    dir_val = DIRECTIONS.get(direction, 0)

    own_device = device is None
    if device is None:
        device = open_device()

    try:
        session_start(device)

        buf = bytearray(PACKET_SIZE)
        buf[0] = REPORT_ID
        buf[1] = 0x13  # CMD_LIGHT
        buf[2] = mode_val
        buf[3] = r
        buf[4] = g
        buf[5] = b
        buf[10] = int(rainbow)
        buf[11] = min(brightness, 5)
        buf[12] = min(speed, 5)
        buf[13] = dir_val
        buf[16] = 0x55
        buf[17] = 0xAA
        send_command(device, bytes(buf))

        session_save(device)
    finally:
        if own_device:
            device.close()


def set_sleep(device: hid.device | None = None, *, timeout: str = "never") -> None:
    """Set the sleep timer."""
    val = SLEEP_VALUES.get(timeout)
    if val is None:
        msg = f"Unknown timeout '{timeout}'. Available: {', '.join(SLEEP_VALUES)}"
        raise ValueError(msg)

    own_device = device is None
    if device is None:
        device = open_device()

    try:
        session_start(device)

        buf = bytearray(PACKET_SIZE)
        buf[0] = REPORT_ID
        buf[1] = 0x17  # CMD_SLEEP
        buf[2] = val
        buf[62] = 0xAA
        buf[63] = 0x55
        send_command(device, bytes(buf))

        session_save(device)
    finally:
        if own_device:
            device.close()


def get_firmware_version(device: hid.device | None = None) -> str:
    """Query firmware version."""
    own_device = device is None
    if device is None:
        device = open_device()

    try:
        session_start(device)
        send_command(device, make_packet(REPORT_ID, 0x01))

        try:
            buf = device.get_feature_report(0x00, 65)
            major, minor, patch = buf[2], buf[3], buf[4]
        except Exception:  # noqa: BLE001
            return "unknown"
        else:
            return f"{major}.{minor}.{patch}"
    finally:
        if own_device:
            device.close()
