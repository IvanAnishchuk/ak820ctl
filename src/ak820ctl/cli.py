"""CLI entry point for ak820ctl."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

import typer
from rich.console import Console

from ak820ctl import __version__
from ak820ctl.commands import (
    LIGHT_MODES,
    SLEEP_VALUES,
    get_device_info,
    read_lighting,
    set_lighting,
    set_sleep,
    sync_time,
)
from ak820ctl.hid import PID, VID, find_device

app = typer.Typer(
    name="ak820ctl",
    help="Control Ajazz AK820 keyboard from Linux (time, LED, sleep).",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

HEX_COLOR_LEN = 6


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
    ] = "ffffff",
    brightness: Annotated[
        int,
        typer.Option("--brightness", "-b", help="Brightness 0-5."),
    ] = 5,
    speed: Annotated[
        int,
        typer.Option("--speed", "-S", help="Animation speed 0-5."),
    ] = 3,
    direction: Annotated[
        str,
        typer.Option("--direction", "-d", help="Direction: left/right/up/down."),
    ] = "left",
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
    if show or mode is None:
        try:
            cfg = read_lighting()
            if not cfg:
                console.print("[yellow]Could not read lighting config[/]")
                raise typer.Exit(1)
            color_hex = f"{cfg['r']:02x}{cfg['g']:02x}{cfg['b']:02x}"
            console.print(f"[bold]Mode:[/] {cfg['mode']}")
            console.print(f"[bold]Color:[/] #{color_hex}")
            console.print(f"[bold]Brightness:[/] {cfg['brightness']}")
            console.print(f"[bold]Speed:[/] {cfg['speed']}")
            console.print(f"[bold]Direction:[/] {cfg['direction']}")
            console.print(f"[bold]Rainbow:[/] {cfg['rainbow']}")
        except RuntimeError as e:
            console.print(f"[red]Error:[/] {e}")
            raise typer.Exit(1) from None
        return

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
        console.print(f"[dim]Device path:[/] {path.decode()}")
        dev_info = get_device_info()
        console.print(f"[dim]Firmware:[/] v{dev_info['firmware']}")
        if "vid" in dev_info:
            console.print(f"[dim]Device VID/PID:[/] {dev_info['vid']:#06x}/{dev_info['pid']:#06x}")
    except RuntimeError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1) from None
