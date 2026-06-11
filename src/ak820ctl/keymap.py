"""Keymap readback for the AK820 keyboard.

Reads the raw keymap buffer the firmware returns via CMD 0x15
(`CMD_READ_KEYMAP`). The wire format is 49 chunks x 64 bytes = 3,136 B
total. Per docs/windows-driver-analysis.md the vendor tool sends the
same 0x15 read before any keymap write to back the existing buffer up
first; we ship the read path here, defer parsing the 4-byte per-slot
encoding (`[type_tag, usage_low, usage_high, modifier]`) and the write
path to a later round (plan2.md Tier E).

The function is structured to mirror `perkey.read_perkey_stored`:
START → CMD → data read → SAVE → END, with the same device open/close
discipline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ak820ctl.commands import CMD_READ_KEYMAP
from ak820ctl.hid import (
    PACKET_SIZE,
    REPORT_ID,
    make_packet,
    open_device,
    read_data,
    send_report,
    session_end,
    session_save,
    session_start,
)

if TYPE_CHECKING:
    import hid

NUM_KEYMAP_CHUNKS = 49
KEYMAP_BYTES = NUM_KEYMAP_CHUNKS * PACKET_SIZE  # 3,136


def parse_keymap_data(packets: list[list[int]]) -> bytes:
    """Strip the hidapi report-ID prefix from each packet and concatenate.

    Pads with `\\x00` if fewer than `NUM_KEYMAP_CHUNKS` packets came back,
    so the caller always sees exactly `KEYMAP_BYTES` bytes. Schema
    decoding (the 4-byte `[type_tag, usage_low, usage_high, modifier]`
    per slot) lands with Tier E.
    """
    raw = bytearray()
    for pkt in packets[:NUM_KEYMAP_CHUNKS]:
        # hidapi prepends a report-ID byte at index 0
        body = pkt[1:] if len(pkt) > PACKET_SIZE else pkt
        raw.extend(body[:PACKET_SIZE])
    if len(raw) < KEYMAP_BYTES:
        raw.extend(b"\x00" * (KEYMAP_BYTES - len(raw)))
    return bytes(raw[:KEYMAP_BYTES])


def read_keymap(device: hid.device | None = None) -> bytes:
    """Read the stored keymap buffer (3,136 raw bytes).

    Sends CMD 0x15 and reads 49 response packets. Per docs/STATUS.md the
    layer distinction (default vs alt) is in the *write* path
    (CMDs 0x11 / 0x27); 0x15 returns the unified buffer.
    """
    own_device = device is None
    if device is None:
        device = open_device()

    try:
        session_start(device)

        cmd = make_packet(
            REPORT_ID, CMD_READ_KEYMAP, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, NUM_KEYMAP_CHUNKS
        )
        send_report(device, cmd)
        packets = read_data(device, CMD_READ_KEYMAP, count=NUM_KEYMAP_CHUNKS)

        # Reset the state machine the same way perkey.read_perkey_stored does.
        session_save(device)
        session_end(device)

        return parse_keymap_data(packets)
    finally:
        if own_device:
            device.close()
