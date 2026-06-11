"""Per-key custom RGB lighting for the AK820 keyboard."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ak820ctl.commands import set_lighting
from ak820ctl.hid import (
    PACKET_SIZE,
    REPORT_ID,
    make_packet,
    open_device,
    read_data,
    send_command,
    send_report,
    session_end,
    session_save,
    session_start,
)
from ak820ctl.models import KeyColor

if TYPE_CHECKING:
    import hid

NUM_KEYS = 144
NUM_PACKETS = 9
ENTRY_SIZE = 4  # pos, R, G, B
MAX_CHANNEL = 255

CMD_CUSTOM_LIGHT = 0x23
CMD_READ_PERKEY = 0xF5
CMD_READ_STORED = 0x22


def build_perkey_data(keys: list[KeyColor]) -> list[bytes]:
    """Build 9 x 64-byte data packets from a list of 144 KeyColor entries.

    Each entry is 4 bytes: [position_index, R, G, B].
    Position index equals the entry's position (0-143).
    """
    if len(keys) != NUM_KEYS:
        msg = f"Expected {NUM_KEYS} keys, got {len(keys)}"
        raise ValueError(msg)

    buf = bytearray(NUM_KEYS * ENTRY_SIZE)
    for pos, key in enumerate(keys):
        off = pos * ENTRY_SIZE
        buf[off] = pos
        buf[off + 1] = key.r
        buf[off + 2] = key.g
        buf[off + 3] = key.b

    packets: list[bytes] = []
    for i in range(NUM_PACKETS):
        start = i * PACKET_SIZE
        packets.append(bytes(buf[start : start + PACKET_SIZE]))
    return packets


def parse_perkey_data(packets: list[list[int]]) -> list[KeyColor]:
    """Parse 9 x 64-byte response packets into 144 KeyColor entries."""
    raw = bytearray()
    for pkt in packets:
        # hidapi prepends report ID byte at index 0
        raw.extend(pkt[1:] if len(pkt) > PACKET_SIZE else pkt)

    keys: list[KeyColor] = []
    for pos in range(NUM_KEYS):
        off = pos * ENTRY_SIZE
        if off + 3 < len(raw):
            keys.append(KeyColor(index=pos, r=raw[off + 1], g=raw[off + 2], b=raw[off + 3]))
        else:
            keys.append(KeyColor(index=pos))
    return keys


def write_perkey(
    keys: list[KeyColor],
    *,
    brightness: int = 5,
    device: hid.device | None = None,
) -> None:
    """Upload per-key colors and activate custom lighting mode (0x80).

    Args:
        keys: 144 KeyColor entries, one per key position.
        brightness: Brightness level 0-5.
        device: HID device. Opened if None.
    """
    packets = build_perkey_data(keys)

    own_device = device is None
    if device is None:
        device = open_device()

    try:
        # Phase 1: Upload per-key data to flash
        session_start(device)

        cmd = make_packet(REPORT_ID, CMD_CUSTOM_LIGHT, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x09)
        send_command(device, cmd)

        for pkt in packets:
            send_command(device, pkt)

        session_save(device)
        session_end(device)

        # Phase 2: Activate per-key custom mode (0x80)
        set_lighting(device, mode="custom", brightness=brightness)
    finally:
        if own_device:
            device.close()


def read_perkey_live(device: hid.device | None = None) -> list[KeyColor]:
    """Read live per-key RGB state (CMD 0xF5). No START needed."""
    own_device = device is None
    if device is None:
        device = open_device()

    try:
        cmd = make_packet(REPORT_ID, CMD_READ_PERKEY, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x09)
        send_report(device, cmd)
        packets = read_data(device, CMD_READ_PERKEY, count=NUM_PACKETS)

        # Reset state machine
        session_save(device)
        session_end(device)

        return parse_perkey_data(packets)
    finally:
        if own_device:
            device.close()


def read_perkey_stored(device: hid.device | None = None) -> list[KeyColor]:
    """Read stored per-key RGB state from flash (CMD 0x22). Needs START."""
    own_device = device is None
    if device is None:
        device = open_device()

    try:
        session_start(device)

        cmd = make_packet(REPORT_ID, CMD_READ_STORED, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x09)
        send_report(device, cmd)
        packets = read_data(device, CMD_READ_STORED, count=NUM_PACKETS)

        # Reset state machine
        session_save(device)
        session_end(device)

        return parse_perkey_data(packets)
    finally:
        if own_device:
            device.close()
