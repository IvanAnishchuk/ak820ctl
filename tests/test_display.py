"""Tests for LCD display image upload."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 — used at runtime (tmp_path fixture)
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from typer.testing import CliRunner

from ak820ctl.cli import app
from ak820ctl.display import (
    CMD_IMAGE,
    DISPLAY_HEIGHT,
    DISPLAY_WIDTH,
    FRAME_BYTES,
    HEADER_SIZE,
    MAX_FRAMES,
    _rgb565_pixel,
    build_header,
    frame_to_rgb565,
    load_animation,
    load_image,
    upload_image,
)
from ak820ctl.hid import DISPLAY_CHUNK_SIZE, REPORT_ID
from tests.conftest import HidDeviceMock, as_hid_device

# ── RGB565 conversion ────────────────────────────────────────────────────────


class TestRgb565Pixel:
    def test_red(self) -> None:
        assert _rgb565_pixel(255, 0, 0) == 0xF800

    def test_green(self) -> None:
        assert _rgb565_pixel(0, 255, 0) == 0x07E0

    def test_blue(self) -> None:
        assert _rgb565_pixel(0, 0, 255) == 0x001F

    def test_white(self) -> None:
        assert _rgb565_pixel(255, 255, 255) == 0xFFFF

    def test_black(self) -> None:
        assert _rgb565_pixel(0, 0, 0) == 0x0000


class TestFrameToRgb565:
    def test_output_size(self) -> None:
        img = Image.new("RGB", (64, 64), (255, 0, 0))
        result = frame_to_rgb565(img)
        assert len(result) == FRAME_BYTES

    def test_solid_red(self) -> None:
        img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), (255, 0, 0))
        result = frame_to_rgb565(img)
        # First pixel: 0xF800 stored little-endian
        assert result[0] == 0x00
        assert result[1] == 0xF8

    def test_solid_blue(self) -> None:
        img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), (0, 0, 255))
        result = frame_to_rgb565(img)
        assert result[0] == 0x1F
        assert result[1] == 0x00

    def test_resizes_to_display_dimensions(self) -> None:
        img = Image.new("RGB", (800, 600), (0, 255, 0))
        result = frame_to_rgb565(img)
        assert len(result) == FRAME_BYTES


# ── Header construction ──────────────────────────────────────────────────────


class TestBuildHeader:
    def test_single_frame(self) -> None:
        header = build_header(1, [1])
        assert len(header) == HEADER_SIZE
        assert header[0] == 1
        assert header[1] == 1
        assert all(b == 0xFF for b in header[2:])

    def test_multi_frame(self) -> None:
        header = build_header(3, [5, 10, 25])
        assert header[0] == 3
        assert header[1] == 5
        assert header[2] == 10
        assert header[3] == 25
        assert all(b == 0xFF for b in header[4:])

    def test_delay_clamping_min(self) -> None:
        header = build_header(1, [0])
        assert header[1] == 1

    def test_delay_clamping_max(self) -> None:
        header = build_header(1, [999])
        assert header[1] == 255

    def test_invalid_frame_count_zero(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            _ = build_header(0, [])

    def test_invalid_frame_count_too_high(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            _ = build_header(MAX_FRAMES + 1, [1] * (MAX_FRAMES + 1))

    def test_mismatched_delays(self) -> None:
        with pytest.raises(ValueError, match="Expected 2 delay values"):
            _ = build_header(2, [1])


# ── Image loading ────────────────────────────────────────────────────────────


class TestLoadImage:
    def test_output_size(self, tmp_path: Path) -> None:
        img = Image.new("RGB", (64, 64), (255, 0, 0))
        path = tmp_path / "test.png"
        img.save(path)
        result = load_image(path)
        assert len(result) == HEADER_SIZE + FRAME_BYTES

    def test_header_format(self, tmp_path: Path) -> None:
        img = Image.new("RGB", (32, 32), (0, 0, 0))
        path = tmp_path / "test.png"
        img.save(path)
        result = load_image(path)
        assert result[0] == 1  # 1 frame
        assert result[1] == 1  # min delay
        assert all(b == 0xFF for b in result[2:HEADER_SIZE])


class TestLoadAnimation:
    def _make_gif(self, tmp_path: Path, n_frames: int, duration: int = 100) -> Path:
        """Create a simple animated GIF with solid color frames."""
        frames = [Image.new("RGB", (32, 32), (i * 50 % 256, 0, 0)) for i in range(n_frames)]
        path = tmp_path / "test.gif"
        frames[0].save(
            path,
            save_all=True,
            append_images=frames[1:],
            duration=duration,
            loop=0,
        )
        return path

    def test_frame_count(self, tmp_path: Path) -> None:
        path = self._make_gif(tmp_path, 3)
        result = load_animation(path)
        assert result[0] == 3

    def test_output_size(self, tmp_path: Path) -> None:
        path = self._make_gif(tmp_path, 3)
        result = load_animation(path)
        assert len(result) == HEADER_SIZE + 3 * FRAME_BYTES

    def test_delay_conversion(self, tmp_path: Path) -> None:
        path = self._make_gif(tmp_path, 2, duration=100)
        result = load_animation(path)
        # 100ms / 2 = 50 (in 2ms units)
        assert result[1] == 50
        assert result[2] == 50

    def test_max_frames_truncation(self, tmp_path: Path) -> None:
        path = self._make_gif(tmp_path, 10)
        result = load_animation(path, max_frames=3)
        assert result[0] == 3
        assert len(result) == HEADER_SIZE + 3 * FRAME_BYTES

    def test_static_image_fallback(self, tmp_path: Path) -> None:
        img = Image.new("RGB", (32, 32), (0, 0, 0))
        path = tmp_path / "static.png"
        img.save(path)
        result = load_animation(path)
        assert result[0] == 1
        assert len(result) == HEADER_SIZE + FRAME_BYTES


# ── Upload protocol ──────────────────────────────────────────────────────────


class TestUploadImage:
    def _make_data(self, n_frames: int = 1) -> bytes:
        """Build minimal valid image data."""
        header = build_header(n_frames, [1] * n_frames)
        frames = b"\x00" * (FRAME_BYTES * n_frames)
        return header + frames

    @patch("ak820ctl.display.open_display_device")
    @patch("ak820ctl.display.open_device")
    @patch("ak820ctl.display.session_end")
    @patch("ak820ctl.display.session_save")
    @patch("ak820ctl.display.session_start")
    @patch("ak820ctl.display.send_command")
    def test_sends_start_image_save_end(
        self,
        mock_send_cmd: MagicMock,
        mock_start: MagicMock,
        mock_save: MagicMock,
        mock_end: MagicMock,
        mock_open_dev: MagicMock,
        mock_open_disp: MagicMock,
    ) -> None:
        cmd_dev = HidDeviceMock()
        disp_dev = HidDeviceMock()
        disp_dev.read.return_value = None
        mock_open_dev.return_value = cmd_dev
        mock_open_disp.return_value = disp_dev

        data = self._make_data()
        upload_image(data)

        mock_start.assert_called_once_with(cmd_dev)
        mock_send_cmd.assert_called_once()
        mock_save.assert_called_once_with(cmd_dev)
        # session_end is required so the device's session state machine doesn't
        # leak into the next command — without it, a subsequent perkey --load
        # was silently dropped and the keyboard stayed dark.
        mock_end.assert_called_once_with(cmd_dev)

    @patch("ak820ctl.display.open_display_device")
    @patch("ak820ctl.display.open_device")
    @patch("ak820ctl.display.session_save")
    @patch("ak820ctl.display.session_start")
    @patch("ak820ctl.display.send_command")
    def test_cmd_image_packet_layout(
        self,
        mock_send_cmd: MagicMock,
        _mock_start: MagicMock,
        _mock_save: MagicMock,
        mock_open_dev: MagicMock,
        mock_open_disp: MagicMock,
    ) -> None:
        cmd_dev = HidDeviceMock()
        disp_dev = HidDeviceMock()
        disp_dev.read.return_value = None
        mock_open_dev.return_value = cmd_dev
        mock_open_disp.return_value = disp_dev

        data = self._make_data()
        upload_image(data, slot=1)

        pkt = cast("list[int]", mock_send_cmd.call_args[0][1])
        assert pkt[0] == REPORT_ID
        assert pkt[1] == CMD_IMAGE
        assert pkt[2] == 1  # slot

    @patch("ak820ctl.display.open_display_device")
    @patch("ak820ctl.display.open_device")
    @patch("ak820ctl.display.session_save")
    @patch("ak820ctl.display.session_start")
    @patch("ak820ctl.display.send_command")
    def test_chunk_count_and_writes(
        self,
        _mock_send_cmd: MagicMock,
        _mock_start: MagicMock,
        _mock_save: MagicMock,
        mock_open_dev: MagicMock,
        mock_open_disp: MagicMock,
    ) -> None:
        cmd_dev = HidDeviceMock()
        disp_dev = HidDeviceMock()
        disp_dev.read.return_value = None
        mock_open_dev.return_value = cmd_dev
        mock_open_disp.return_value = disp_dev

        data = self._make_data()
        expected_chunks = -(-len(data) // DISPLAY_CHUNK_SIZE)
        upload_image(data)

        assert disp_dev.write.call_count == expected_chunks
        assert disp_dev.read.call_count == expected_chunks

    @patch("ak820ctl.display.open_display_device")
    @patch("ak820ctl.display.open_device")
    @patch("ak820ctl.display.session_save")
    @patch("ak820ctl.display.session_start")
    @patch("ak820ctl.display.send_command")
    def test_chunk_report_format(
        self,
        _mock_send_cmd: MagicMock,
        _mock_start: MagicMock,
        _mock_save: MagicMock,
        mock_open_dev: MagicMock,
        mock_open_disp: MagicMock,
    ) -> None:
        cmd_dev = HidDeviceMock()
        disp_dev = HidDeviceMock()
        disp_dev.read.return_value = None
        mock_open_dev.return_value = cmd_dev
        mock_open_disp.return_value = disp_dev

        data = self._make_data()
        upload_image(data)

        # Each write should be report_id(0x00) + 4096 bytes
        first_write = cast("bytes", disp_dev.write.call_args_list[0][0][0])
        assert len(first_write) == DISPLAY_CHUNK_SIZE + 1
        assert first_write[0] == 0x00

    @patch("ak820ctl.display.open_display_device")
    @patch("ak820ctl.display.open_device")
    @patch("ak820ctl.display.session_save")
    @patch("ak820ctl.display.session_start")
    @patch("ak820ctl.display.send_command")
    def test_progress_callback(
        self,
        _mock_send_cmd: MagicMock,
        _mock_start: MagicMock,
        _mock_save: MagicMock,
        mock_open_dev: MagicMock,
        mock_open_disp: MagicMock,
    ) -> None:
        cmd_dev = HidDeviceMock()
        disp_dev = HidDeviceMock()
        disp_dev.read.return_value = None
        mock_open_dev.return_value = cmd_dev
        mock_open_disp.return_value = disp_dev

        data = self._make_data()
        expected_chunks = -(-len(data) // DISPLAY_CHUNK_SIZE)
        callback = MagicMock()
        upload_image(data, progress_callback=callback)

        assert callback.call_count == expected_chunks
        callback.assert_any_call(1, expected_chunks)
        callback.assert_called_with(expected_chunks, expected_chunks)

    @patch("ak820ctl.display.open_display_device")
    @patch("ak820ctl.display.open_device")
    @patch("ak820ctl.display.session_save")
    @patch("ak820ctl.display.session_start")
    @patch("ak820ctl.display.send_command")
    def test_closes_devices_on_success(
        self,
        _mock_send_cmd: MagicMock,
        _mock_start: MagicMock,
        _mock_save: MagicMock,
        mock_open_dev: MagicMock,
        mock_open_disp: MagicMock,
    ) -> None:
        cmd_dev = HidDeviceMock()
        disp_dev = HidDeviceMock()
        disp_dev.read.return_value = None
        mock_open_dev.return_value = cmd_dev
        mock_open_disp.return_value = disp_dev

        upload_image(self._make_data())

        cmd_dev.close.assert_called_once()
        disp_dev.close.assert_called_once()

    def test_uses_provided_devices(self) -> None:
        cmd_dev = HidDeviceMock()
        disp_dev = HidDeviceMock()
        disp_dev.read.return_value = None

        with (
            patch("ak820ctl.display.session_start"),
            patch("ak820ctl.display.send_command"),
            patch("ak820ctl.display.session_save"),
        ):
            upload_image(
                self._make_data(),
                cmd_device=as_hid_device(cmd_dev),
                disp_device=as_hid_device(disp_dev),
            )

        # Should NOT close devices we didn't open
        cmd_dev.close.assert_not_called()
        disp_dev.close.assert_not_called()


# ── CLI tests ────────────────────────────────────────────────────────────────


class TestCli:
    def test_image_file_not_found(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["image", "/nonexistent/file.png"])
        assert result.exit_code == 1
        assert "File not found" in result.output

    def test_gif_file_not_found(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["gif", "/nonexistent/file.gif"])
        assert result.exit_code == 1
        assert "File not found" in result.output

    def test_image_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["image", "--help"])
        assert result.exit_code == 0
        assert "LCD" in result.output

    def test_gif_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["gif", "--help"])
        assert result.exit_code == 0
        assert "GIF" in result.output or "LCD" in result.output
