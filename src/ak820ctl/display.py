"""LCD display image and animation upload for the AK820 keyboard."""

from __future__ import annotations

import logging
import math
import time
from typing import TYPE_CHECKING

from PIL import Image

from ak820ctl.hid import (
    DISPLAY_ACK_TIMEOUT_MS,
    DISPLAY_CHUNK_SIZE,
    FW_DELAY,
    REPORT_ID,
    make_packet,
    open_device,
    open_display_device,
    send_command,
    session_save,
    session_start,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import hid

logger = logging.getLogger(__name__)

# Display hardware parameters (AK820 Pro)
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 128
FRAME_BYTES = DISPLAY_WIDTH * DISPLAY_HEIGHT * 2  # RGB565, 2 bytes/pixel
HEADER_SIZE = 256
MAX_FRAMES = 141
MAX_SLOT = 255
CMD_IMAGE = 0x72


def _rgb565_pixel(r: int, g: int, b: int) -> int:
    """Convert a single RGB888 pixel to RGB565."""
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def frame_to_rgb565(img: Image.Image) -> bytes:
    """Resize a PIL Image to display dimensions and convert to RGB565-LE bytes."""
    resized = img.resize((DISPLAY_WIDTH, DISPLAY_HEIGHT), Image.Resampling.NEAREST)
    rgb_img = resized.convert("RGB")
    pixels = rgb_img.tobytes()

    buf = bytearray(FRAME_BYTES)
    for i in range(DISPLAY_WIDTH * DISPLAY_HEIGHT):
        offset = i * 3
        val = _rgb565_pixel(pixels[offset], pixels[offset + 1], pixels[offset + 2])
        buf[i * 2] = val & 0xFF
        buf[i * 2 + 1] = val >> 8
    return bytes(buf)


def build_header(frame_count: int, delays: list[int]) -> bytes:
    """Build the 256-byte image header.

    Args:
        frame_count: Number of frames (1-141).
        delays: Per-frame delay values in 2ms units (1-255 each).
    """
    if frame_count < 1 or frame_count > MAX_FRAMES:
        msg = f"Frame count {frame_count} out of range (1-{MAX_FRAMES})"
        raise ValueError(msg)
    if len(delays) != frame_count:
        msg = f"Expected {frame_count} delay values, got {len(delays)}"
        raise ValueError(msg)

    header = bytearray([0xFF] * HEADER_SIZE)
    header[0] = frame_count
    for i, d in enumerate(delays):
        header[1 + i] = max(1, min(255, d))
    return bytes(header)


def load_image(path: Path) -> bytes:
    """Load a static image, resize to display size, return header + RGB565 data."""
    with Image.open(path) as img:
        frame_data = frame_to_rgb565(img.convert("RGB"))
    header = build_header(1, [1])
    return header + frame_data


def load_animation(path: Path, *, max_frames: int = MAX_FRAMES) -> bytes:
    """Load an animated GIF, return header + RGB565 data for all frames."""
    with Image.open(path) as img:
        if not getattr(img, "is_animated", False):
            frame_data = frame_to_rgb565(img.convert("RGB"))
            header = build_header(1, [1])
            return header + frame_data

        n_frames_total: int = getattr(img, "n_frames", 1)
        n_frames = min(n_frames_total, max_frames)

        delays: list[int] = []
        frames_data = bytearray()

        for i in range(n_frames):
            img.seek(i)
            duration_ms: int = img.info.get("duration", 50)
            delay_val = max(1, min(255, duration_ms // 2))
            delays.append(delay_val)

            frame_rgb = img.convert("RGB")
            frames_data.extend(frame_to_rgb565(frame_rgb))

    header = build_header(n_frames, delays)
    return header + bytes(frames_data)


def _read_display_ack(disp_device: hid.device) -> None:
    """Read ACK from display interface with timeout.

    CRITICAL: Uses device.read(), NOT get_feature_report().
    Using get_feature_report on Interface 2 crashes the firmware.
    """
    try:
        data = disp_device.read(65, timeout_ms=DISPLAY_ACK_TIMEOUT_MS)
        if data:
            logger.debug("Display ACK: %d bytes", len(data))
        else:
            logger.debug("Display ACK timeout, continuing")
    except OSError:
        logger.debug("Display ACK read error, continuing")


def upload_image(
    data: bytes,
    *,
    slot: int = 1,
    cmd_device: hid.device | None = None,
    disp_device: hid.device | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> None:
    """Upload image data (header + frames) to the keyboard LCD.

    Args:
        data: Complete image data (256-byte header + RGB565 frame data).
        slot: LCD slot index (1-based).
        cmd_device: Interface 3 command device. Opened if None.
        disp_device: Interface 2 display device. Opened if None.
        progress_callback: Called with (chunks_done, total_chunks) after each chunk.
    """
    if not 1 <= slot <= MAX_SLOT:
        msg = f"Slot {slot} out of range (1-{MAX_SLOT})"
        raise ValueError(msg)
    if len(data) < HEADER_SIZE:
        msg = f"Data too short ({len(data)} bytes, minimum {HEADER_SIZE})"
        raise ValueError(msg)

    total = len(data)
    n_chunks = math.ceil(total / DISPLAY_CHUNK_SIZE)

    own_cmd = cmd_device is None
    own_disp = disp_device is None
    try:
        if cmd_device is None:
            cmd_device = open_device()
        if disp_device is None:
            disp_device = open_display_device()

        # Step 1: CMD_START on Interface 3
        session_start(cmd_device)

        # Step 2: CMD_IMAGE on Interface 3 with slot and chunk count
        chunk_lo = n_chunks & 0xFF
        chunk_hi = (n_chunks >> 8) & 0xFF
        image_cmd = make_packet(REPORT_ID, CMD_IMAGE, slot, 0, 0, 0, 0, 0, chunk_lo, chunk_hi)
        send_command(cmd_device, image_cmd)

        # Step 3: Send data chunks on Interface 2 via output reports
        for i in range(n_chunks):
            offset = i * DISPLAY_CHUNK_SIZE
            chunk = data[offset : offset + DISPLAY_CHUNK_SIZE]

            # Pad last chunk with zeros if needed
            if len(chunk) < DISPLAY_CHUNK_SIZE:
                chunk = chunk + b"\x00" * (DISPLAY_CHUNK_SIZE - len(chunk))

            # Output report: report ID 0x00 + 4096 bytes data
            report = b"\x00" + chunk
            disp_device.write(report)
            _read_display_ack(disp_device)
            time.sleep(FW_DELAY)

            if progress_callback is not None:
                progress_callback(i + 1, n_chunks)

        # Step 4: CMD_SAVE on Interface 3
        session_save(cmd_device)
    finally:
        if own_disp and disp_device is not None:
            disp_device.close()
        if own_cmd and cmd_device is not None:
            cmd_device.close()
