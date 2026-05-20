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

logger = logging.getLogger(__name__)


def find_device() -> bytes:
    """Find the AK820 HID device path for Interface 3."""
    for dev in hid.enumerate(VID, PID):
        if dev["interface_number"] == INTERFACE:
            return dev["path"]
    msg = (
        f"AK820 not found (VID={VID:#06x} PID={PID:#06x} Interface {INTERFACE}). "
        "Is the keyboard connected via USB?"
    )
    raise RuntimeError(msg)


def open_device(path: bytes | None = None) -> hid.device:
    """Open the AK820 command interface."""
    if path is None:
        path = find_device()
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
    send_command(device, make_packet(REPORT_ID, 0x18))


def session_save(device: hid.device) -> None:
    """Send CMD_SAVE (0x02)."""
    send_command(device, make_packet(REPORT_ID, 0x02))


def session_end(device: hid.device) -> None:
    """Send CMD_FINISH (0xF0)."""
    send_command(device, make_packet(REPORT_ID, 0xF0))
