"""Shared test fixtures.

The fixtures here exist to remove a class of `reportAny` warnings from
the test suite: every place that constructs a `MagicMock` of a `hid.device`
and accesses its methods previously had pyright complaining that the
attribute access was `Any`. `HidDeviceMock` assigns each child mock as a
real attribute in `__init__`, so pyright recovers `MagicMock` (not `Any`)
for `mock.send_feature_report.call_args` and friends.

We deliberately do NOT pass `spec=hid.device` to the base `MagicMock` —
spec= would force `__getattr__` back to lazily-created `Any` attributes
and undo the typing benefit. Runtime safety against typos comes from the
explicit per-method assignments here; if a test calls a method we didn't
declare, it'll get an auto-mock (same as plain `MagicMock`).

The factory helpers (`ack_packet`, `device_info_packet`) replace the
inline 65-byte list construction that was repeated across
`test_commands.py`, `test_perkey.py`, and `test_display.py`. They use
named keyword arguments so a test only spells out the bytes it cares about.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


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
