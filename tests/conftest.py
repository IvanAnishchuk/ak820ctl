"""Shared test fixtures.

The fixtures here exist to remove a class of `reportAny` warnings from
the test suite: every place that constructs a `MagicMock` of a `hid.device`
and accesses its methods previously had pyright complaining that the
attribute access was `Any`. `HidDeviceMock` assigns each child mock as a
real attribute in `__init__`, so pyright recovers `MagicMock` (not `Any`)
for `mock.send_feature_report.call_args` and friends.

`HidDeviceMock` is a plain class (NOT a `MagicMock` subclass) with no
`__getattr__`, so accessing a method we didn't declare in `__init__`
raises `AttributeError` instead of auto-creating a child mock. That's
intentional: the trade-off for the typed-attribute benefit is losing
`MagicMock`'s lazy method discovery. If `ak820ctl` calls a new
`hid.device` method, add it to `__init__`.

The factory helpers (`ack_packet`, `device_info_packet`,
`perkey_response_packets`) build the 65-byte feature-report payloads
used as `get_feature_report.side_effect` values; `perkey_response_packets`
is used by `test_perkey.py`, the other two by `test_commands.py`.
Named keyword arguments let each call site spell out only the bytes
it cares about.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import pytest

from ak820ctl.perkey import build_perkey_data

if TYPE_CHECKING:
    import hid

    from ak820ctl.models import KeyColor


class HidDeviceMock:
    """A typed container of child `MagicMock`s shaped like `hid.device`.

    Deliberately NOT a `MagicMock` subclass: we want pyright to recover
    `MagicMock` for each method-attribute access (e.g.
    `mock.send_feature_report.call_count`), but `MagicMock.__getattr__`
    is typed as `Any` and overrides any class-level annotations on a
    subclass. A plain class with explicit attribute assignments in
    `__init__` solves both problems — runtime callability comes from
    the child `MagicMock`s, static types come from the annotations.

    Methods covered are the subset of `hid.device` actually called by
    `src/ak820ctl/`; add to this list if a new call site appears.
    """

    def __init__(self) -> None:
        self.get_feature_report: MagicMock = MagicMock(return_value=[0] * 65)
        self.get_input_report: MagicMock = MagicMock(return_value=[0] * 65)
        self.send_feature_report: MagicMock = MagicMock(return_value=0)
        self.read: MagicMock = MagicMock(return_value=[])
        self.write: MagicMock = MagicMock(return_value=0)
        self.open: MagicMock = MagicMock(return_value=None)
        self.open_path: MagicMock = MagicMock(return_value=None)
        self.close: MagicMock = MagicMock(return_value=None)
        self.set_nonblocking: MagicMock = MagicMock(return_value=0)
        self.error: MagicMock = MagicMock(return_value=None)


@pytest.fixture
def mock_hid_device() -> HidDeviceMock:
    """A `HidDeviceMock` with sensible no-op defaults.

    Override per-test by setting `mock.<method>.return_value` or
    `.side_effect = [...]` as usual.
    """
    return HidDeviceMock()


def as_hid_device(mock: HidDeviceMock) -> hid.device:
    """Cast a `HidDeviceMock` to `hid.device` for call sites typed against
    the real `hid.device` class.

    `HidDeviceMock` is structurally compatible (same method names, same
    callable shapes) but pyright won't accept it nominally — there's no
    inheritance. Routing through `object` first makes the cast
    intentional (silences `reportInvalidCast`).
    """
    return cast("hid.device", cast("object", mock))


# ── Feature-report payload factories ───────────────────────────────────────


def ack_packet(cmd: int = 0x04) -> list[int]:
    """65-byte feature-report ACK echo: `[0x00, 0x04, cmd] + [0x00]*62`.

    Mirrors the response shape used by the AK820 firmware after a
    SET_REPORT — the first byte is the hidapi-prepended report ID (0x00),
    then 64 bytes of payload.
    """
    pkt = [0x00] * 65
    pkt[1] = 0x04
    pkt[2] = cmd
    return pkt


def device_info_packet(
    *,
    vid: int = 0x0C45,
    pid: int = 0x8009,
    fw_major: int = 1,
    fw_minor: int = 20,
    capabilities: int = 0x3040,
) -> list[int]:
    """65-byte CMD 0x05 device-info response with VID/PID/FW/caps at
    the wire offsets parsed by `commands.get_device_info`.
    """
    pkt = [0x00] * 65
    pkt[1] = capabilities & 0xFF
    pkt[2] = (capabilities >> 8) & 0xFF
    pkt[5] = vid & 0xFF
    pkt[6] = (vid >> 8) & 0xFF
    pkt[7] = pid & 0xFF
    pkt[8] = (pid >> 8) & 0xFF
    pkt[9] = fw_minor & 0xFF
    pkt[10] = fw_major & 0xFF
    pkt[11] = 0xFF
    pkt[12] = 0xFF
    return pkt


def perkey_response_packets(keys: list[KeyColor]) -> list[list[int]]:
    """Build the 9 x 65-byte response packets that the device returns to
    CMD_READ_PERKEY / CMD_READ_STORED, encoding the given `keys`.

    Each entry on the wire is 4 bytes: [position, R, G, B]. The hidapi
    layer prepends a 0x00 report-ID prefix to each packet, so the returned
    payloads are 65 bytes (1 + 64). This is exactly the shape that
    `parse_perkey_data` decodes back into a `list[KeyColor]`.
    """
    raw = build_perkey_data(keys)
    return [[0x00, *pkt] for pkt in raw]


def keymap_response_packets(payload: bytes) -> list[list[int]]:
    """Build 49 x 65-byte response packets for `CMD_READ_KEYMAP` (0x15).

    `payload` is the raw 3,136-byte keymap buffer; the firmware splits it
    into 49 x 64-byte packets, each prefixed by the hidapi 0x00 report-ID
    byte. Shorter payloads pad with zero, longer ones are truncated.
    """
    chunks: list[list[int]] = []
    for i in range(49):
        start = i * 64
        chunk = bytes(payload[start : start + 64])
        if len(chunk) < 64:
            chunk = chunk + b"\x00" * (64 - len(chunk))
        chunks.append([0x00, *chunk])
    return chunks
