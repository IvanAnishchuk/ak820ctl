"""Tests for HID packet construction."""

from __future__ import annotations

from ak820ctl.hid import PACKET_SIZE, REPORT_ID, make_packet


def test_make_packet_default_size() -> None:
    pkt = make_packet(0x04, 0x18)
    assert len(pkt) == PACKET_SIZE
    assert pkt[0] == 0x04
    assert pkt[1] == 0x18
    assert all(b == 0 for b in pkt[2:])


def test_make_packet_custom_size() -> None:
    pkt = make_packet(0xFF, size=8)
    assert len(pkt) == 8
    assert pkt[0] == 0xFF
    assert all(b == 0 for b in pkt[1:])


def test_make_packet_multiple_bytes() -> None:
    pkt = make_packet(0x04, 0x28, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01)
    assert pkt[0] == REPORT_ID
    assert pkt[1] == 0x28
    assert pkt[8] == 0x01


def test_report_id_constant() -> None:
    assert REPORT_ID == 0x04


def test_packet_size_constant() -> None:
    assert PACKET_SIZE == 64
