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


# Safety bound: how many ACK-echo packets `read_data` will drain before it
# gives up and returns whatever data it has. The firmware empirically emits
# 0-1 ACK echoes per request, but a stuck queue can hold more after a
# mutation that left state dangling. 16 is generous without being unbounded.
MAX_ACK_DRAINS = 16

# Minimum packet length required to fingerprint an ACK echo (we read up to
# pkt[8] in `_is_ack_echo`).
_ACK_ECHO_MIN_LEN = 9


def _is_ack_echo(pkt: list[int], cmd_byte: int) -> bool:
    """Return True if `pkt` looks like the firmware's echo of our request.

    The vendor firmware echoes the request packet back as the first
    response on the GET_REPORT pipe. After the hidapi report-id prefix
    (`pkt[0] == 0x00`), the echo starts with `[REPORT_ID, cmd_byte, 0x00,
    <varbyte>, 0x00, 0x00, 0x00, 0x00, ...]`. The four-zero stretch at
    `pkt[5:9]` mirrors the unused arg bytes of `make_packet` and combined
    with the leading prefix + REPORT_ID + cmd_byte + the post-cmd zero
    gives us a strong fingerprint that real data packets are very unlikely
    to hit.
    """
    return (
        len(pkt) >= _ACK_ECHO_MIN_LEN
        and pkt[0] == 0
        and pkt[1] == REPORT_ID
        and pkt[2] == cmd_byte
        and pkt[3] == 0
        and pkt[5] == 0
        and pkt[6] == 0
        and pkt[7] == 0
        and pkt[8] == 0
    )


def read_data(device: hid.device, cmd_byte: int, count: int = 1) -> list[list[int]]:
    """Read `count` data packets in response to CMD `cmd_byte`.

    Classifies each feature-report packet by shape rather than position:
    packets matching the ACK-echo signature for `cmd_byte` are drained,
    everything else is treated as data. This tolerates either ACK-first
    or data-first ordering on the kernel queue, which empirically varies
    across calls on the same device handle (see CHANGELOG: read_data
    ACK-ordering fix).

    Drains at most `MAX_ACK_DRAINS` echoes before giving up; an OSError
    from `get_feature_report` ends the read and returns what was collected.
    """
    packets: list[list[int]] = []
    drained = 0
    for _ in range(count + MAX_ACK_DRAINS):
        if len(packets) >= count:
            break
        try:
            pkt = device.get_feature_report(0x00, 65)
        except OSError:
            logger.debug("read_data: get_feature_report failed")
            break
        time.sleep(FW_DELAY)
        if _is_ack_echo(pkt, cmd_byte):
            if drained >= MAX_ACK_DRAINS:
                # Hit the bound — this packet is the (MAX_ACK_DRAINS+1)-th
                # echo, and we refuse to keep draining. Don't count it so
                # the trailing summary log reports the configured bound
                # exactly, not one over.
                logger.debug(
                    "read_data: drained MAX_ACK_DRAINS (%d) echoes for CMD 0x%02x "
                    "without data; giving up",
                    MAX_ACK_DRAINS,
                    cmd_byte,
                )
                break
            drained += 1
            continue
        packets.append(pkt)
    if drained:
        logger.debug(
            "read_data: drained %d ACK echo(es) for CMD 0x%02x before %d data packet(s)",
            drained,
            cmd_byte,
            len(packets),
        )
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
