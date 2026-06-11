"""Low-level HID communication with the Ajazz AK820 keyboard."""

from __future__ import annotations

import logging
import time

import hid

VID = 0x0C45
PID = 0x8009
INTERFACE = 3
PACKET_SIZE = 64
REPORT_ID = 0x04
FW_DELAY = 0.035  # 35ms mandatory inter-command delay

# Display data channel (Interface 2)
DISPLAY_USAGE_PAGE = 0xFF68
DISPLAY_PAYLOAD_SIZE = 4096  # RGB565 data per chunk — what works on V1.14
DISPLAY_ACK_TIMEOUT_MS = 300

# Back-compat alias: cli.py reports `--max-chunk` against the payload size,
# not the wire size. Will be removed in a future release.
DISPLAY_CHUNK_SIZE = DISPLAY_PAYLOAD_SIZE

# Canonical 4123-byte chunk form (4096 payload + 27-byte 0xFF trailer)
# from docs/PROTOCOL.md §LCD Image Upload + sibling impls
# (epomaker-ak820-pro, ajazz-keyboard-linux-cpp). Tried live on V1.14
# firmware: every render came out garbled. Left commented for the next
# round if a different firmware turns up — uncomment + flip the chunk
# loop in display.py to test again.
# DISPLAY_TRAILER_SIZE = 27  # noqa: ERA001
# DISPLAY_TRAILER_BYTE = 0xFF  # noqa: ERA001
# DISPLAY_CHUNK_WIRE_SIZE = DISPLAY_PAYLOAD_SIZE + DISPLAY_TRAILER_SIZE  # 4123  # noqa: ERA001

# Session-control opcodes (issued by session_start/save/end below).
CMD_START = 0x18
CMD_SAVE = 0x02
CMD_END = 0xF0

# VIA-mode dual-identity that AK820 Pro also enumerates as (see docs/PROTOCOL.md
# §VIA-mode variant). We don't talk to this surface — surfaced in error
# messages so a confused user knows what they're looking at.
VIA_VID = 0x3151
VIA_PID = 0x4021

logger = logging.getLogger(__name__)


def find_device() -> bytes:
    """Find the AK820 HID device path for Interface 3."""
    for dev in hid.enumerate(VID, PID):
        if dev["interface_number"] == INTERFACE:
            return dev["path"]
    msg = (
        f"AK820 not found (VID={VID:#06x} PID={PID:#06x} Interface {INTERFACE}). "
        "Is the keyboard connected via USB? "
        f"(If it enumerates as VID={VIA_VID:#06x} PID={VIA_PID:#06x} it's in "
        "VIA mode — ak820ctl doesn't support that surface; mode-switch "
        "mechanism still unknown, see docs/PROTOCOL.md.)"
    )
    raise RuntimeError(msg)


def open_device(path: bytes | None = None) -> hid.device:
    """Open the AK820 command interface."""
    if path is None:
        path = find_device()
    device = hid.device()
    device.open_path(path)
    return device


DISPLAY_INTERFACE = 2


def find_display_device() -> bytes:
    """Find the AK820 HID device path for Interface 2 (display data channel).

    Tries usage page first (more robust), falls back to interface number
    when the hidapi backend doesn't report usage pages (e.g. Linux hidraw).
    """
    for dev in hid.enumerate(VID, PID):
        if dev.get("usage_page") == DISPLAY_USAGE_PAGE:
            return dev["path"]
    # Fallback: match by interface number
    for dev in hid.enumerate(VID, PID):
        if dev.get("interface_number") == DISPLAY_INTERFACE:
            return dev["path"]
    msg = (
        f"AK820 display interface not found (VID={VID:#06x} PID={PID:#06x} "
        f"Interface {DISPLAY_INTERFACE}). Is the keyboard connected via USB?"
    )
    raise RuntimeError(msg)


def open_display_device(path: bytes | None = None) -> hid.device:
    """Open the AK820 display data interface (Interface 2).

    IMPORTANT: Only use write() and read() on this device.
    NEVER use get_feature_report() — it crashes the firmware.
    """
    if path is None:
        path = find_display_device()
    device = hid.device()
    device.open_path(path)
    return device


def make_packet(*args: int, size: int = PACKET_SIZE) -> bytes:
    """Build a zero-padded packet from the given byte values."""
    buf = bytearray(size)
    for i, val in enumerate(args):
        buf[i] = val
    return bytes(buf)


def send_report(device: hid.device, data: bytes) -> None:
    """Send a feature report with delay. No GET_REPORT handshake."""
    report = b"\x00" + data
    _ = device.send_feature_report(report)
    time.sleep(FW_DELAY)


def send_command(device: hid.device, data: bytes) -> None:
    """Send a feature report, do the GET_REPORT handshake.

    The inter-command delay is handled by send_report(); only one additional
    delay after the handshake GET_REPORT is needed.
    """
    send_report(device, data)

    # GET_REPORT handshake (response is discarded; STALLs are expected)
    try:
        _ = device.get_feature_report(0x00, 65)
    except OSError:
        logger.debug("GET_REPORT handshake STALL (expected for some commands)")


def read_data(device: hid.device, count: int = 1) -> list[list[int]]:
    """Read data packets after a command, discarding the initial ACK.

    The first GET_REPORT after a read command is an echo/ACK — discard it.
    Then read `count` actual data packets.
    """
    # Discard ACK
    try:
        _ = device.get_feature_report(0x00, 65)
    except OSError:
        logger.debug("ACK read failed")
    time.sleep(FW_DELAY)

    packets: list[list[int]] = []
    for _ in range(count):
        try:
            pkt = device.get_feature_report(0x00, 65)
            packets.append(pkt)
        except OSError:
            logger.debug("Data packet read failed")
            break
        time.sleep(FW_DELAY)

    return packets


def session_start(device: hid.device) -> None:
    """Send CMD_START (0x18)."""
    send_command(device, make_packet(REPORT_ID, CMD_START))


def session_save(device: hid.device) -> None:
    """Send CMD_SAVE (0x02)."""
    send_command(device, make_packet(REPORT_ID, CMD_SAVE))


def session_end(device: hid.device) -> None:
    """Send CMD_END (0xF0)."""
    send_command(device, make_packet(REPORT_ID, CMD_END))
