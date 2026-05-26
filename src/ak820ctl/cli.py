"""CLI entry point for ak820ctl."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from pydantic import TypeAdapter, ValidationError
from rich.console import Console
from rich.progress import Progress

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
from ak820ctl.display import MAX_FRAMES, MAX_SLOT, load_animation, load_image, upload_image
from ak820ctl.hid import DISPLAY_CHUNK_SIZE, PID, VID, find_device
from ak820ctl.models import KeyboardDump, KeyColor
from ak820ctl.perkey import NUM_KEYS, read_perkey_live, read_perkey_stored, write_perkey

app = typer.Typer(
    name="ak820ctl",
    help="Control Ajazz AK820 keyboard from Linux (time, LED, sleep).",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

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
    if len(color_hex) != HEX_RGB_LEN:
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


HEX_RGB_LEN = 6


def _parse_hex_color(color: str) -> tuple[int, int, int]:
    """Parse a hex color string like 'ff0000' into (R, G, B)."""
    c = color.lstrip("#")
    if len(c) != HEX_RGB_LEN:
        msg = f"Color must be 6 hex digits (e.g. ff0000), got: {color}"
        raise ValueError(msg)
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _parse_key_spec(spec: str, num_keys: int) -> tuple[int, tuple[int, int, int]]:
    """Parse 'INDEX:RRGGBB' into (index, (R, G, B))."""
    if ":" not in spec:
        msg = f"Invalid key spec: {spec} (expected INDEX:RRGGBB)"
        raise ValueError(msg)
    idx_str, color_str = spec.split(":", 1)
    idx = int(idx_str)
    if not 0 <= idx < num_keys:
        msg = f"Key index must be 0-{num_keys - 1}, got: {idx}"
        raise ValueError(msg)
    return idx, _parse_hex_color(color_str)


_KEY_COLOR_LIST_ADAPTER = TypeAdapter(list[KeyColor])


def _load_colors_file(path: Path, num_keys: int) -> list[KeyColor]:
    """Load per-key colors from JSON file, validated via pydantic."""
    entries = _KEY_COLOR_LIST_ADAPTER.validate_json(path.read_bytes())
    keys = [KeyColor(index=i) for i in range(num_keys)]
    for entry in entries:
        keys[entry.index] = entry
    return keys


@app.command()
def perkey(
    all_color: Annotated[
        str | None,
        typer.Option("--all", "-a", help="Set all keys to this RGB hex color."),
    ] = None,
    key: Annotated[
        list[str] | None,
        typer.Option("--key", "-k", help="Set key by index: INDEX:RRGGBB (e.g. 42:ff0000)."),
    ] = None,
    file: Annotated[
        Path | None,
        typer.Option("--file", "-f", help="Load per-key colors from JSON file."),
    ] = None,
    dump: Annotated[
        bool,
        typer.Option("--dump", "-d", help="Dump live per-key state to JSON."),
    ] = False,
    dump_stored: Annotated[
        bool,
        typer.Option("--dump-stored", help="Dump stored per-key state from flash."),
    ] = False,
    brightness: Annotated[
        int,
        typer.Option("--brightness", "-b", help="Brightness 0-5 (for write operations)."),
    ] = 5,
) -> None:
    """Read or set per-key custom RGB colors (144 keys).

    With no options, displays the live per-key state.
    """
    # Read modes
    if dump or dump_stored:
        try:
            keys_data = read_perkey_stored() if dump_stored else read_perkey_live()
        except RuntimeError as e:
            console.print(f"[red]Error:[/] {e}")
            raise typer.Exit(1) from None
        data = [k.model_dump() for k in keys_data]
        console.print(json.dumps(data, indent=2))
        return

    # Build keys list based on mode
    keys_list: list[KeyColor] | None = None
    label = ""

    try:
        if all_color is not None:
            r, g, b = _parse_hex_color(all_color)
            keys_list = [KeyColor(index=i, r=r, g=g, b=b) for i in range(NUM_KEYS)]
            label = f"All {NUM_KEYS} keys set to #{all_color.lstrip('#')}"
        elif key is not None:
            keys_list = list(read_perkey_live())
            for spec in key:
                idx, (r, g, b) = _parse_key_spec(spec, NUM_KEYS)
                keys_list[idx] = KeyColor(index=idx, r=r, g=g, b=b)
            label = f"Updated {len(key)} key(s)"
        elif file is not None:
            if not file.exists():
                console.print(f"[red]File not found:[/] {file}")
                raise typer.Exit(1)
            keys_list = _load_colors_file(file, NUM_KEYS)
            label = f"Loaded per-key colors from {file}"
    except (ValueError, TypeError, RuntimeError, ValidationError) as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1) from None

    if keys_list is not None:
        try:
            write_perkey(keys_list, brightness=brightness)
            console.print(f"[green]{label}[/]")
        except RuntimeError as e:
            console.print(f"[red]Error:[/] {e}")
            raise typer.Exit(1) from None
        return

    # Default: show live state
    try:
        keys_data = read_perkey_live()
    except RuntimeError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1) from None
    active = [k for k in keys_data if k.r or k.g or k.b]
    if not active:
        console.print("[dim]No per-key colors active (all black)[/]")
    else:
        console.print(f"[bold]{len(active)} key(s) with color:[/]")
        for k in active:
            console.print(f"  [dim]{k.index:3d}:[/] #{k.r:02x}{k.g:02x}{k.b:02x}")


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
    There is no known command to restore the default display.
    Turn the wheel button to switch to another screen and back.
    """
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
    ] = MAX_FRAMES,
) -> None:
    """Upload an animated GIF to the keyboard LCD (128x128, max 141 frames).

    WARNING: This replaces the firmware's built-in status screen.
    There is no known command to restore the default display.
    Turn the wheel button to switch to another screen and back.
    """
    if not file.exists():
        console.print(f"[red]File not found:[/] {file}")
        raise typer.Exit(1)
    if not 1 <= slot <= MAX_SLOT:
        console.print(f"[red]Slot must be 1-255, got:[/] {slot}")
        raise typer.Exit(1)
    if max_frames < 1:
        console.print(f"[red]max-frames must be >= 1, got:[/] {max_frames}")
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
