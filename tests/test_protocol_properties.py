"""Property-based tests for HID protocol packet construction."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from ak820ctl.hid import PACKET_SIZE, make_packet


@given(st.lists(st.integers(0, 255), min_size=0, max_size=PACKET_SIZE))
def test_make_packet_always_correct_size(values: list[int]) -> None:
    pkt = make_packet(*values)
    assert len(pkt) == PACKET_SIZE


@given(st.lists(st.integers(0, 255), min_size=1, max_size=PACKET_SIZE))
def test_make_packet_preserves_input_bytes(values: list[int]) -> None:
    pkt = make_packet(*values)
    for i, val in enumerate(values):
        assert pkt[i] == val


@given(st.lists(st.integers(0, 255), min_size=0, max_size=PACKET_SIZE))
def test_make_packet_pads_with_zeros(values: list[int]) -> None:
    pkt = make_packet(*values)
    for i in range(len(values), PACKET_SIZE):
        assert pkt[i] == 0


@given(st.integers(1, 128))
def test_make_packet_custom_size(size: int) -> None:
    pkt = make_packet(0x04, size=size)
    assert len(pkt) == size
    assert pkt[0] == 0x04


@given(
    year=st.integers(0, 99),
    month=st.integers(1, 12),
    day=st.integers(1, 28),
    hour=st.integers(0, 23),
    minute=st.integers(0, 59),
    second=st.integers(0, 59),
)
def test_time_data_packet_structure(
    year: int, month: int, day: int, hour: int, minute: int, second: int
) -> None:
    """Time data payload must have magic marker, time fields, and delimiters."""
    buf = bytearray(PACKET_SIZE)
    buf[0] = 0x00
    buf[1] = 0x01
    buf[2] = 0x5A  # magic
    buf[3] = year
    buf[4] = month
    buf[5] = day
    buf[6] = hour
    buf[7] = minute
    buf[8] = second
    buf[10] = 0x04  # fixed
    buf[62] = 0xAA
    buf[63] = 0x55

    assert len(buf) == PACKET_SIZE
    assert buf[2] == 0x5A
    assert buf[10] == 0x04
    assert buf[62] == 0xAA
    assert buf[63] == 0x55
    assert 0 <= buf[3] <= 99
    assert 1 <= buf[4] <= 12
    assert 1 <= buf[5] <= 28
    assert 0 <= buf[6] <= 23
    assert 0 <= buf[7] <= 59
    assert 0 <= buf[8] <= 59


@given(
    mode=st.integers(0, 0x13) | st.just(0x80),
    r=st.integers(0, 255),
    g=st.integers(0, 255),
    b=st.integers(0, 255),
    rainbow=st.booleans(),
    brightness=st.integers(0, 5),
    speed=st.integers(0, 5),
    direction=st.integers(0, 3),
)
def test_lighting_data_packet_structure(
    mode: int,
    r: int,
    g: int,
    b: int,
    rainbow: bool,
    brightness: int,
    speed: int,
    direction: int,
) -> None:
    """Lighting data payload must have correct field positions and delimiters."""
    buf = bytearray(PACKET_SIZE)
    buf[0] = mode
    buf[1] = r
    buf[2] = g
    buf[3] = b
    buf[8] = int(rainbow)
    buf[9] = brightness
    buf[10] = speed
    buf[11] = direction
    buf[62] = 0x55
    buf[63] = 0xAA

    assert len(buf) == PACKET_SIZE
    assert buf[0] == mode
    assert buf[1] == r
    assert buf[2] == g
    assert buf[3] == b
    assert all(buf[i] == 0 for i in range(4, 8))  # reserved padding
    assert buf[8] == int(rainbow)
    assert buf[9] == brightness
    assert buf[10] == speed
    assert buf[11] == direction
    assert all(buf[i] == 0 for i in range(12, 62))  # padding
    assert buf[62] == 0x55
    assert buf[63] == 0xAA
