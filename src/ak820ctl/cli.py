"""CLI entry point for ak820ctl."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ak820ctl import __version__
from ak820ctl.commands import (
    LIGHT_MODES,
    SLEEP_VALUES,
    dump_settings,
    get_device_info,
    read_lighting,
    restore_settings,
    set_lighting,
    set_sleep,
    sync_time,
)
from ak820ctl.display import MAX_FRAMES, MAX_SLOT
from ak820ctl.hid import PID, VID, find_device
from ak820ctl.models import KeyboardDump

app = typer.Typer(
    name="ak820ctl",
    help="Control Ajazz AK820 keyboard from Linux (time, LED, sleep).",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

HEX_COLOR_LEN = 6
DEFAULT_COLOR = "ffffff"
DEFAULT_BRIGHTNESS = 5
DEFAULT_SPEED = 3
DEFAULT_DIRECTION = "left"


def version_callback(value: bool) -> None:
    if value:
        console.print(f"ak820ctl {__version__}")
        raise typer.Exit


@app.callback()
def main(
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = False,
) -> None:
    """Control Ajazz AK820 keyboard from Linux."""


@app.command()
def time(
    set_time: Annotated[
        str | None,
        typer.Option(
            "--set",
            "-s",
            help="Time to set (HH:MM:SS or YYYY-MM-DD HH:MM:SS). Default: now.",
        ),
    ] = None,
) -> None:
    """Sync the keyboard clock. Sets to current system time by default."""
    dt = None
    if set_time:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%H:%M:%S", "%Y-%m-%d %H:%M", "%H:%M"):
            try:
                dt = datetime.strptime(set_time, fmt)
                if "%Y" not in fmt:
                    now = datetime.now()
                    dt = dt.replace(year=now.year, month=now.month, day=now.day)
                break
            except ValueError:
                continue
        if dt is None:
            console.print(f"[red]Cannot parse time:[/] {set_time}")
            raise typer.Exit(1)

    try:
        synced = sync_time(dt=dt)
        console.print(f"[green]Clock synced:[/] {synced:%Y-%m-%d %H:%M:%S}")
    except RuntimeError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1) from None


@app.command()
def light(
    mode: Annotated[str | None, typer.Argument(help="Lighting mode name.")] = None,
    color: Annotated[
        str,
        typer.Option("--color", "-c", help="RGB hex color (e.g. ff0000)."),
    ] = DEFAULT_COLOR,
    brightness: Annotated[
        int,
        typer.Option("--brightness", "-b", help="Brightness 0-5."),
    ] = DEFAULT_BRIGHTNESS,
    speed: Annotated[
        int,
        typer.Option("--speed", "-S", help="Animation speed 0-5."),
    ] = DEFAULT_SPEED,
    direction: Annotated[
        str,
        typer.Option("--direction", "-d", help="Direction: left/right/up/down."),
    ] = DEFAULT_DIRECTION,
    rainbow: Annotated[
        bool,
        typer.Option("--rainbow", "-r", help="Enable rainbow mode."),
    ] = False,
    show: Annotated[
        bool,
        typer.Option("--show", "-s", help="Read and display current lighting config."),
    ] = False,
) -> None:
    """Set or read keyboard lighting mode.

    With no arguments, shows current config (same as --show).

    Modes: off, static, breath, spectrum, ripples, flowing, glittering,
    falling, colourful, outward, scrolling, rolling, rotating, explode,
    launch, pulsating, tilt, shuttle, single-on, single-off, custom.
    """
    # Only enter show mode if --show was passed, or if no arguments at all
    # (mode is None and all other options are at their defaults)
    defaults = (
        color == DEFAULT_COLOR
        and brightness == DEFAULT_BRIGHTNESS
        and speed == DEFAULT_SPEED
        and direction == DEFAULT_DIRECTION
        and not rainbow
    )
    if show or (mode is None and defaults):
        try:
            cfg = read_lighting()
            console.print(f"[bold]Mode:[/] {cfg.mode}")
            console.print(f"[bold]Color:[/] #{cfg.r:02x}{cfg.g:02x}{cfg.b:02x}")
            console.print(f"[bold]Brightness:[/] {cfg.brightness}")
            console.print(f"[bold]Speed:[/] {cfg.speed}")
            console.print(f"[bold]Direction:[/] {cfg.direction}")
            console.print(f"[bold]Rainbow:[/] {cfg.rainbow}")
        except RuntimeError as e:
            console.print(f"[red]Error:[/] {e}")
            raise typer.Exit(1) from None
        return

    # Default to "static" when options are passed without an explicit mode
    if mode is None:
        mode = "static"

    if mode not in LIGHT_MODES:
        console.print(f"[red]Unknown mode:[/] {mode}")
        console.print(f"Available: {', '.join(LIGHT_MODES)}")
        raise typer.Exit(1)

    color_hex = color.lstrip("#")
    if len(color_hex) != HEX_COLOR_LEN:
        console.print("[red]Color must be 6 hex digits[/] (e.g. ff0000)")
        raise typer.Exit(1)
    r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)

    try:
        set_lighting(
            mode=mode,
            r=r,
            g=g,
            b=b,
            rainbow=rainbow,
            brightness=brightness,
            speed=speed,
            direction=direction,
        )
        console.print(f"[green]Lighting set:[/] {mode} (#{color_hex}, brightness={brightness})")
    except RuntimeError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1) from None


@app.command()
def sleep(
    timeout: Annotated[
        str,
        typer.Argument(help="Sleep timeout: never, 1min, 5min, 30min."),
    ] = "never",
) -> None:
    """Set the keyboard sleep timer."""
    if timeout not in SLEEP_VALUES:
        console.print(f"[red]Unknown timeout:[/] {timeout}")
        console.print(f"Available: {', '.join(SLEEP_VALUES)}")
        raise typer.Exit(1)

    try:
        set_sleep(timeout=timeout)
        console.print(f"[green]Sleep timer set:[/] {timeout}")
    except RuntimeError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1) from None


@app.command()
def info() -> None:
    """Show keyboard connection info and firmware version."""
    try:
        path = find_device()
        console.print(f"[green]Found AK820:[/] VID={VID:#06x} PID={PID:#06x}")
        console.print(f"[dim]Device path:[/] {path.decode(errors='replace')}")
        dev_info = get_device_info()
        console.print(f"[dim]Firmware:[/] v{dev_info.firmware}")
        if dev_info.vid:
            console.print(f"[dim]Device VID/PID:[/] {dev_info.vid:#06x}/{dev_info.pid:#06x}")
    except RuntimeError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1) from None


@app.command()
def dump(
    output: Annotated[
        str | None,
        typer.Option("--output", "-o", help="Output file path. Default: stdout."),
    ] = None,
) -> None:
    """Dump all keyboard settings to JSON."""
    try:
        data = dump_settings()
    except RuntimeError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1) from None

    if output:
        try:
            data.save(Path(output))
        except OSError as e:
            console.print(f"[red]Cannot write file:[/] {e}")
            raise typer.Exit(1) from None
        console.print(f"[green]Settings saved to:[/] {output}")
    else:
        console.print(data.model_dump_json(indent=2))


@app.command()
def image(
    file: Annotated[Path, typer.Argument(help="Image file (PNG, JPG, BMP, etc.).")],
    slot: Annotated[
        int,
        typer.Option("--slot", "-s", help="LCD slot index."),
    ] = 1,
) -> None:
    """Upload a static image to the keyboard LCD (128x128).

    WARNING: This replaces the firmware's built-in status screen.
    There is no known command to restore the default display —
    power-cycle the keyboard (unplug and replug USB) to get it back.
    """
    from rich.progress import Progress  # noqa: PLC0415

    from ak820ctl.display import load_image, upload_image  # noqa: PLC0415
    from ak820ctl.hid import DISPLAY_CHUNK_SIZE  # noqa: PLC0415

    if not file.exists():
        console.print(f"[red]File not found:[/] {file}")
        raise typer.Exit(1)
    if not 1 <= slot <= MAX_SLOT:
        console.print(f"[red]Slot must be 1-255, got:[/] {slot}")
        raise typer.Exit(1)

    try:
        data = load_image(file)
    except (OSError, ValueError) as e:
        console.print(f"[red]Cannot load image:[/] {e}")
        raise typer.Exit(1) from None

    n_chunks = -(-len(data) // DISPLAY_CHUNK_SIZE)
    try:
        with Progress(console=console) as progress:
            task = progress.add_task("Uploading...", total=n_chunks)

            def _on_progress(done: int, _total: int) -> None:
                progress.update(task, completed=done)

            upload_image(data, slot=slot, progress_callback=_on_progress)
        console.print(f"[green]Image uploaded to slot {slot}[/]")
    except RuntimeError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1) from None


@app.command()
def gif(
    file: Annotated[Path, typer.Argument(help="Animated GIF file.")],
    slot: Annotated[
        int,
        typer.Option("--slot", "-s", help="LCD slot index."),
    ] = 1,
    max_frames: Annotated[
        int,
        typer.Option("--max-frames", help="Maximum number of frames to upload."),
    ] = 141,
) -> None:
    """Upload an animated GIF to the keyboard LCD (128x128, max 141 frames).

    WARNING: This replaces the firmware's built-in status screen.
    There is no known command to restore the default display —
    power-cycle the keyboard (unplug and replug USB) to get it back.
    """
    from rich.progress import Progress  # noqa: PLC0415

    from ak820ctl.display import load_animation, upload_image  # noqa: PLC0415
    from ak820ctl.hid import DISPLAY_CHUNK_SIZE  # noqa: PLC0415

    if not file.exists():
        console.print(f"[red]File not found:[/] {file}")
        raise typer.Exit(1)
    if not 1 <= slot <= MAX_SLOT:
        console.print(f"[red]Slot must be 1-255, got:[/] {slot}")
        raise typer.Exit(1)
    max_frames = min(max_frames, MAX_FRAMES)

    try:
        data = load_animation(file, max_frames=max_frames)
    except (OSError, ValueError) as e:
        console.print(f"[red]Cannot load animation:[/] {e}")
        raise typer.Exit(1) from None

    n_frames = data[0]
    console.print(f"[dim]Loaded {n_frames} frame(s)[/]")

    n_chunks = -(-len(data) // DISPLAY_CHUNK_SIZE)
    try:
        with Progress(console=console) as progress:
            task = progress.add_task("Uploading...", total=n_chunks)

            def _on_progress(done: int, _total: int) -> None:
                progress.update(task, completed=done)

            upload_image(data, slot=slot, progress_callback=_on_progress)
        console.print(f"[green]Animation uploaded to slot {slot}[/] ({n_frames} frames)")
    except RuntimeError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1) from None


@app.command()
def restore(
    input_file: Annotated[str, typer.Argument(help="JSON file to restore from.")],
    skip_time: Annotated[
        bool,
        typer.Option("--skip-time", help="Don't sync the clock."),
    ] = False,
) -> None:
    """Restore keyboard settings from a JSON dump."""
    path = Path(input_file)
    if not path.exists():
        console.print(f"[red]File not found:[/] {input_file}")
        raise typer.Exit(1)

    try:
        data = KeyboardDump.load(path)
    except (OSError, ValueError) as e:
        console.print(f"[red]Cannot read dump file:[/] {e}")
        raise typer.Exit(1) from None

    try:
        actions = restore_settings(data, skip_time=skip_time)
        for action in actions:
            console.print(f"[green]Restored:[/] {action}")
    except RuntimeError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1) from None
