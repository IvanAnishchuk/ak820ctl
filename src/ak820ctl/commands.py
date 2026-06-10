"""High-level commands for the AK820 keyboard."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from ak820ctl.hid import (
    PACKET_SIZE,
    REPORT_ID,
    make_packet,
    open_device,
    read_data,
    send_command,
    send_report,
    session_save,
    session_start,
)
from ak820ctl.models import DeviceInfo, KeyboardDump, LightingConfig

if TYPE_CHECKING:
    import hid

# Command opcodes (CMD byte at packet[1] following REPORT_ID).
# Names follow docs/PROTOCOL.md and docs/STATUS.md. Session-control
# (CMD_START/SAVE/END) live in hid.py; per-key (perkey.py) and LCD
# (display.py) opcodes stay with their respective modules.
CMD_READ_ID = 0x05  # Returns VID/PID/firmware + capabilities
CMD_READ_LIGHTING = 0x12
CMD_SET_LIGHTING = 0x13  # Also writes flash @ 0x9800 (persists power-cycle)
CMD_SET_SLEEP = 0x17
CMD_SET_TIME = 0x28

# Reverse-engineered. CMD_READ_KEYMAP is wired through ak820ctl.keymap
# (used by `keymap --dump`); the rest are parked for the keymap-write
# path (plan2.md Tier E).
CMD_KEYMAP_DEFAULT = 0x11  # V1.13 only — writes flash @ 0x9400
CMD_READ_KEYMAP = 0x15  # 49 chunks x 64 B = 3,136 B
CMD_CUSTOM_LIGHTING_PREAMBLE = 0x20  # Sets firmware state byte 0x32
CMD_KEYMAP_ALT = 0x27  # Writes flash @ 0xAC00


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

        # Step 2: CMD_SET_TIME preamble (0x28)
        preamble = make_packet(REPORT_ID, CMD_SET_TIME, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01)
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
    """Set the keyboard lighting mode.

    CMD 0x13 also writes the lighting config to flash at 0x9800, so the
    setting persists across power cycles — there is no transient-only
    variant.
    """
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

        # Step 1: CMD_SET_LIGHTING preamble (0x13), arg2=0x01 means data follows
        preamble = make_packet(
            REPORT_ID, CMD_SET_LIGHTING, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01
        )
        send_command(device, preamble)

        # Step 2: Lighting data payload (report ID = mode, NOT 0x04)
        buf = bytearray(PACKET_SIZE)
        buf[0] = mode_val
        buf[1] = r
        buf[2] = g
        buf[3] = b
        # bytes 4-7: reserved (zero)
        buf[8] = int(rainbow)
        buf[9] = min(brightness, 5)
        buf[10] = min(speed, 5)
        buf[11] = dir_val
        # bytes 12-61: padding (zero)
        buf[62] = 0x55  # delimiter
        buf[63] = 0xAA
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
        buf[1] = CMD_SET_SLEEP
        buf[2] = val
        buf[62] = 0xAA
        buf[63] = 0x55
        send_command(device, bytes(buf))

        session_save(device)
    finally:
        if own_device:
            device.close()


LIGHT_MODE_NAMES: dict[int, str] = {v: k for k, v in LIGHT_MODES.items()}
DIRECTION_NAMES: dict[int, str] = {v: k for k, v in DIRECTIONS.items()}


def get_device_info(device: hid.device | None = None) -> DeviceInfo:
    """Query device ID: capabilities, VID, PID, firmware version.

    Uses CMD 0x05 which returns the full ID payload.
    Response (after hidapi report ID byte 0):
      bytes 1-2: capabilities (LE uint16)
      bytes 5-6: USB VID (LE)
      bytes 7-8: USB PID (LE)
      bytes 9-10: firmware version (LE uint16, major.minor)
      bytes 11-12: end marker (0xFFFF)
    """
    own_device = device is None
    if device is None:
        device = open_device()

    try:
        send_report(
            device,
            make_packet(REPORT_ID, CMD_READ_ID, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01),
        )
        packets = read_data(device, count=1)
        if not packets:
            return DeviceInfo()

        buf = packets[0]
        # hidapi prepends report ID byte at index 0, so offsets are +1 from raw HID
        vid = buf[5] | (buf[6] << 8)
        pid = buf[7] | (buf[8] << 8)
        fw_raw = buf[9] | (buf[10] << 8)
        fw_major = fw_raw >> 8
        fw_minor = fw_raw & 0xFF

        return DeviceInfo(
            vid=vid,
            pid=pid,
            firmware=f"{fw_major}.{fw_minor:02d}",
            firmware_raw=fw_raw,
            capabilities=buf[1] | (buf[2] << 8),
        )
    finally:
        if own_device:
            device.close()


def get_firmware_version(device: hid.device | None = None) -> str:
    """Query firmware version (convenience wrapper)."""
    return get_device_info(device).firmware


def read_lighting(device: hid.device | None = None) -> LightingConfig:
    """Read current lighting configuration from the keyboard."""
    own_device = device is None
    if device is None:
        device = open_device()

    try:
        send_report(
            device,
            make_packet(REPORT_ID, CMD_READ_LIGHTING, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01),
        )
        packets = read_data(device, count=1)
        if not packets:
            return LightingConfig()

        buf = packets[0]
        # hidapi prepends report ID byte at index 0, so data starts at index 1
        mode_val = buf[1]
        return LightingConfig(
            mode=LIGHT_MODE_NAMES.get(mode_val, f"0x{mode_val:02x}"),
            mode_value=mode_val,
            r=buf[2],
            g=buf[3],
            b=buf[4],
            rainbow=bool(buf[9]),
            brightness=min(buf[10], 5),
            speed=min(buf[11], 5),
            direction=DIRECTION_NAMES.get(buf[12], str(buf[12])),
        )
    finally:
        if own_device:
            device.close()


def dump_settings(device: hid.device | None = None) -> KeyboardDump:
    """Read all available settings from the keyboard."""
    own_device = device is None
    if device is None:
        device = open_device()

    try:
        return KeyboardDump(
            device=get_device_info(device),
            lighting=read_lighting(device),
        )
    finally:
        if own_device:
            device.close()


def restore_settings(
    dump: KeyboardDump,
    device: hid.device | None = None,
    *,
    skip_time: bool = False,
) -> list[str]:
    """Apply settings from a dump. Returns list of actions taken."""
    own_device = device is None
    if device is None:
        device = open_device()

    actions: list[str] = []
    try:
        cfg = dump.lighting
        # Fall back to mode_value if mode string is unknown (e.g. "0x1f")
        mode = (
            cfg.mode if cfg.mode in LIGHT_MODES else LIGHT_MODE_NAMES.get(cfg.mode_value, "static")
        )
        set_lighting(
            device,
            mode=mode,
            r=cfg.r,
            g=cfg.g,
            b=cfg.b,
            rainbow=cfg.rainbow,
            brightness=cfg.brightness,
            speed=cfg.speed,
            direction=cfg.direction,
        )
        actions.append(f"lighting: {mode}")

        if not skip_time:
            _ = sync_time(device)
            actions.append("time: synced")
    finally:
        if own_device:
            device.close()

    return actions
