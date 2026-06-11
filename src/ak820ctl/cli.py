"""CLI entry point for ak820ctl."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from importlib import resources
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
from ak820ctl.hid import (
    DISPLAY_CHUNK_SIZE,
    PACKET_SIZE,
    PID,
    REPORT_ID,
    VID,
    find_device,
    make_packet,
    open_device,
    read_data,
    send_report,
    session_end,
)
from ak820ctl.keymap import KEYMAP_BYTES, NUM_KEYMAP_CHUNKS, read_keymap
from ak820ctl.keys import KEY_INDEX, Key
from ak820ctl.models import KeyboardDump, KeyColor, ThemeSource
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


def parse_hex_color(color: str) -> tuple[int, int, int]:
    """Parse a hex color string like 'ff0000' into (R, G, B)."""
    c = color.lstrip("#")
    if len(c) != HEX_RGB_LEN:
        msg = f"Color must be 6 hex digits (e.g. ff0000), got: {color}"
        raise ValueError(msg)
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def parse_key_spec(spec: str, num_keys: int) -> tuple[int, tuple[int, int, int]]:
    """Parse 'INDEX:RRGGBB' into (index, (R, G, B))."""
    if ":" not in spec:
        msg = f"Invalid key spec: {spec} (expected INDEX:RRGGBB)"
        raise ValueError(msg)
    idx_str, color_str = spec.split(":", 1)
    idx = int(idx_str)
    if not 0 <= idx < num_keys:
        msg = f"Key index must be 0-{num_keys - 1}, got: {idx}"
        raise ValueError(msg)
    return idx, parse_hex_color(color_str)


_KEY_COLOR_LIST_ADAPTER = TypeAdapter(list[KeyColor])

# Conventional sentinel: a single dash means stdin (when reading) or stdout
# (when writing), so pipelines like `theme-compile X | perkey --load -` work
# without needing /dev/stdin.
STDIO_PATH = Path("-")


def _is_stdio(path: Path) -> bool:
    return str(path) == "-"


def _read_input_bytes(path: Path) -> bytes:
    """Read bytes from `path`, or stdin if `path` is `-`."""
    if _is_stdio(path):
        return sys.stdin.buffer.read()
    return path.read_bytes()


def _load_colors_file(path: Path, num_keys: int) -> list[KeyColor]:
    """Load per-key colors from JSON, validated via pydantic. `-` means stdin."""
    entries = _KEY_COLOR_LIST_ADAPTER.validate_json(_read_input_bytes(path))
    keys = [KeyColor(index=i) for i in range(num_keys)]
    for entry in entries:
        keys[entry.index] = entry
    return keys


def _save_perkey_state(path: Path) -> None:
    """Read live per-key state and save to JSON file. `-` means stdout."""
    try:
        keys_data = read_perkey_live()
    except RuntimeError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1) from None
    payload = json.dumps([k.model_dump() for k in keys_data], indent=2) + "\n"
    if _is_stdio(path):
        # Plain stdout, not rich UI: this is machine-readable JSON for a pipe.
        print(payload, end="")  # noqa: T201
        return
    try:
        _ = path.write_text(payload, encoding="utf-8")
    except OSError as e:
        console.print(f"[red]Cannot write file:[/] {e}")
        raise typer.Exit(1) from None
    console.print(f"[green]Per-key state saved to:[/] {path}")


def _dump_perkey_state(*, stored: bool) -> None:
    """Read per-key state and print JSON to stdout."""
    try:
        keys_data = read_perkey_stored() if stored else read_perkey_live()
    except RuntimeError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1) from None
    data = [k.model_dump() for k in keys_data]
    console.print(json.dumps(data, indent=2))


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
    load: Annotated[
        Path | None,
        typer.Option("--load", "-l", help="Load per-key colors from JSON file."),
    ] = None,
    save: Annotated[
        Path | None,
        typer.Option("--save", "-s", help="Save live per-key state to JSON file."),
    ] = None,
    dump: Annotated[
        bool,
        typer.Option("--dump", "-d", help="Dump live per-key state to JSON (stdout)."),
    ] = False,
    dump_stored: Annotated[
        bool,
        typer.Option("--dump-stored", help="Dump stored per-key state from flash (stdout)."),
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
    if save is not None:
        _save_perkey_state(save)
        return

    if dump or dump_stored:
        _dump_perkey_state(stored=dump_stored)
        return

    # Build keys list based on mode
    keys_list: list[KeyColor] | None = None
    label = ""

    try:
        if all_color is not None:
            r, g, b = parse_hex_color(all_color)
            keys_list = [KeyColor(index=i, r=r, g=g, b=b) for i in range(NUM_KEYS)]
            label = f"All {NUM_KEYS} keys set to #{all_color.lstrip('#')}"
        elif key is not None:
            # Parse all specs up front so a malformed spec fails fast without
            # making a device round-trip — also lets the test suite cover
            # parse errors without a keyboard attached.
            parsed_specs = [parse_key_spec(spec, NUM_KEYS) for spec in key]
            keys_list = list(read_perkey_live())
            for idx, (r, g, b) in parsed_specs:
                keys_list[idx] = KeyColor(index=idx, r=r, g=g, b=b)
            label = f"Updated {len(key)} key(s)"
        elif load is not None:
            if not _is_stdio(load) and not load.exists():
                console.print(f"[red]File not found:[/] {load}")
                raise typer.Exit(1)
            keys_list = _load_colors_file(load, NUM_KEYS)
            label = (
                "Loaded per-key colors from stdin"
                if _is_stdio(load)
                else (f"Loaded per-key colors from {load}")
            )
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


def _format_keymap_payload(data: bytes) -> str:
    """JSON envelope around raw keymap bytes: hex string + declared size."""
    return json.dumps({"size": len(data), "hex": data.hex()}, indent=2) + "\n"


@app.command()
def keymap(
    dump: Annotated[
        bool,
        typer.Option("--dump", "-d", help="Dump raw keymap bytes as JSON to stdout."),
    ] = False,
    save: Annotated[
        Path | None,
        typer.Option("--save", "-s", help="Save raw keymap bytes to JSON file (`-` is stdout)."),
    ] = None,
) -> None:
    """Read the stored keymap buffer (3,136 raw bytes, CMD 0x15).

    Per-slot decoding ([type_tag, usage_low, usage_high, modifier]) and
    the write path (CMDs 0x11 / 0x27) are not yet exposed — see
    plan2.md Tier E.
    """
    if not dump and save is None:
        console.print("[yellow]No action selected.[/] Pass --dump for stdout or --save PATH.")
        raise typer.Exit(1)

    try:
        data = read_keymap()
    except RuntimeError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1) from None

    if len(data) != KEYMAP_BYTES:
        console.print(f"[yellow]Warning:[/] expected {KEYMAP_BYTES} keymap bytes, got {len(data)}")

    payload = _format_keymap_payload(data)

    if save is None or _is_stdio(save):
        # Plain stdout for pipe-friendliness; rich UI only for status lines.
        print(payload, end="")  # noqa: T201
        return

    try:
        _ = save.write_text(payload, encoding="utf-8")
    except OSError as e:
        console.print(f"[red]Cannot write file:[/] {e}")
        raise typer.Exit(1) from None
    console.print(f"[green]Keymap saved to:[/] {save}")


# Whitelist of opcodes the `probe` subcommand will issue. All are
# documented as read-only in docs/STATUS.md / docs/unknown-commands.md
# (the 0x10/0x14/0x16/0x26/0xE0 ones are unused by the vendor tool but
# return a response without side-effects per Phase 3 analysis).
PROBE_SAFE_CMDS: tuple[int, ...] = (0x05, 0x10, 0x12, 0x14, 0x15, 0x16, 0x26, 0xE0)

# Refused with a clear error: these write flash or persist state.
PROBE_DESTRUCTIVE_CMDS: dict[int, str] = {
    0x11: "CMD_KEYMAP_DEFAULT — writes flash @ 0x9400 (V1.13 only)",
    0x13: "CMD_SET_LIGHTING — writes flash @ 0x9800",
    0x23: "CMD_WRITE_PERKEY — writes per-key buffer",
    0x27: "CMD_KEYMAP_ALT — writes flash @ 0xAC00",
    0x38: "unknown — vendor tool never sends; treat as destructive",
}

PROBE_HEX_PREVIEW_BYTES = 32  # first N bytes of each response shown inline

# Packet-count argument the firmware expects in CMD byte[9] for each
# read opcode, and the matching number of response packets to read back.
# Documented opcodes use what the production read paths use; the rest
# default to PROBE_DEFAULT_COUNT (1).
PROBE_DEFAULT_COUNT = 1
PROBE_COUNTS: dict[int, int] = {
    0x05: 1,  # CMD_READ_ID — single-packet device info
    0x12: 1,  # CMD_READ_LIGHTING — single-packet lighting config
    0x14: 48,  # 48-chunk read per docs/unknown-commands.md (vendor tool never sends)
    0x15: NUM_KEYMAP_CHUNKS,  # CMD_READ_KEYMAP — 49 x 64 B
}


def probe_one(cmd_byte: int) -> list[list[int]]:
    """Send one safe read command and collect the response packets."""
    count = PROBE_COUNTS.get(cmd_byte, PROBE_DEFAULT_COUNT)
    device = open_device()
    try:
        send_report(
            device,
            make_packet(REPORT_ID, cmd_byte, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, count),
        )
        packets = read_data(device, count=count)
        # End the session so a subsequent probe isn't dropped silently.
        session_end(device)
    finally:
        device.close()
    return packets


def format_probe_summary(cmd_byte: int, packets: list[list[int]]) -> str:
    n_payload = sum(len(p) for p in packets)
    if not packets:
        return f"CMD 0x{cmd_byte:02x}: 0 packets (no response)"
    head = bytes(packets[0][1 : 1 + PROBE_HEX_PREVIEW_BYTES]).hex()
    return f"CMD 0x{cmd_byte:02x}: {len(packets)} packet(s), {n_payload} B; head: {head}"


def write_probe_response(out_dir: Path, cmd_byte: int, packets: list[list[int]]) -> None:
    raw = bytearray()
    for pkt in packets:
        # strip the hidapi report-ID prefix the same way parse_keymap_data does
        body = pkt[1:] if len(pkt) > PACKET_SIZE else pkt
        raw.extend(body[:PACKET_SIZE])
    out_path = out_dir / f"cmd_{cmd_byte:02x}.bin"
    _ = out_path.write_bytes(bytes(raw))


@app.command()
def probe(
    cmd: Annotated[
        str | None,
        typer.Option(
            "--cmd",
            help="Single CMD opcode to probe as hex (e.g. 0x15). Must be in the safe whitelist.",
        ),
    ] = None,
    all_cmds: Annotated[
        bool,
        typer.Option("--all", help="Probe every safe CMD in the whitelist."),
    ] = False,
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir",
            help="Directory to dump raw response bytes per CMD (one file per opcode).",
        ),
    ] = None,
) -> None:
    """Send safe read-only CMDs and print their response shapes.

    Useful for live verification of canonical findings without leaving
    the project. Refuses destructive opcodes (0x11 / 0x13 / 0x23 / 0x27 /
    0x38). The keymap-write / per-key-write paths land later (plan2.md
    Tier E) with `--confirm` gating.
    """
    if cmd is None and not all_cmds:
        console.print("[yellow]No action selected.[/] Pass --cmd HEX or --all.")
        raise typer.Exit(1)

    targets: list[int] = []
    if all_cmds:
        targets = list(PROBE_SAFE_CMDS)
    if cmd is not None:
        try:
            cmd_int = int(cmd, 16)
        except ValueError:
            console.print(f"[red]Invalid hex value for --cmd:[/] {cmd}")
            raise typer.Exit(1) from None
        if cmd_int in PROBE_DESTRUCTIVE_CMDS:
            why = PROBE_DESTRUCTIVE_CMDS[cmd_int]
            console.print(
                f"[red]Refusing destructive CMD 0x{cmd_int:02x}:[/] {why}."
                f" Destructive opcodes will land behind --confirm in a later release."
            )
            raise typer.Exit(1)
        if cmd_int not in PROBE_SAFE_CMDS:
            allowed = ", ".join(f"0x{c:02x}" for c in PROBE_SAFE_CMDS)
            console.print(
                f"[red]CMD 0x{cmd_int:02x} not in the safe whitelist.[/] Allowed: {allowed}"
            )
            raise typer.Exit(1)
        if cmd_int not in targets:
            targets.append(cmd_int)

    if output_dir is not None:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            console.print(f"[red]Cannot create output dir:[/] {e}")
            raise typer.Exit(1) from None

    for cmd_byte in targets:
        try:
            packets = probe_one(cmd_byte)
        except RuntimeError as e:
            console.print(f"[red]CMD 0x{cmd_byte:02x} failed:[/] {e}")
            continue
        console.print(format_probe_summary(cmd_byte, packets))
        if output_dir is not None:
            write_probe_response(output_dir, cmd_byte, packets)
    if output_dir is not None:
        console.print(f"[green]Probe responses written to:[/] {output_dir}")


def _read_data_text(*parts: str) -> str:
    """Read a bundled data file by path components under `ak820ctl/data/`."""
    traversable = resources.files("ak820ctl") / "data"
    for p in parts:
        traversable = traversable / p
    return traversable.read_text(encoding="utf-8")


_LAYOUT_ADAPTER = TypeAdapter(dict[str, list[Key]])


def load_layout(path: Path | None = None) -> dict[str, list[Key]]:
    """Load and validate a layout file. None uses bundled simple layout.

    Each value list is coerced to `list[Key]`; an unknown key name raises
    `pydantic.ValidationError` citing the bad name.
    """
    text = (
        path.read_text(encoding="utf-8")
        if path is not None
        else _read_data_text("layouts", "simple.json")
    )
    return _LAYOUT_ADAPTER.validate_json(text)


def compile_theme(
    source: ThemeSource,
    layout: dict[str, list[Key]],
) -> list[KeyColor]:
    """Build 144 KeyColor entries from a theme source.

    Order of precedence (lowest first): base, groups, overrides.
    Raises ValueError if a group name is not in the layout. Override key
    names are validated at `ThemeSource` parse time (enum coercion).
    """
    br, bg, bb = parse_hex_color(source.base)
    keys = [KeyColor(index=i, r=br, g=bg, b=bb) for i in range(NUM_KEYS)]

    for group_name, color_hex in source.groups.items():
        if group_name not in layout:
            msg = f"Unknown group {group_name!r} (not defined in layout)"
            raise ValueError(msg)
        r, g, b = parse_hex_color(color_hex)
        for key in layout[group_name]:
            idx = KEY_INDEX[key]
            keys[idx] = KeyColor(index=idx, r=r, g=g, b=b)

    for key, color_hex in source.overrides.items():
        r, g, b = parse_hex_color(color_hex)
        idx = KEY_INDEX[key]
        keys[idx] = KeyColor(index=idx, r=r, g=g, b=b)

    return keys


@app.command(name="theme-compile")
def theme_compile(
    source: Annotated[
        Path,
        typer.Argument(help="Theme source JSON file (`-` for stdin)."),
    ],
    layout: Annotated[
        Path | None,
        typer.Option("--layout", help="Layout JSON [default: bundled simple.json]."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file [default: stdout, `-` is also stdout]."),
    ] = None,
) -> None:
    """Compile a theme source into a 144-slot per-key JSON file.

    Use `-` for `source` to read from stdin, or `-o -` to write to stdout
    explicitly. See src/ak820ctl/data/README.md for theme source format.
    """
    if not _is_stdio(source) and not source.exists():
        console.print(f"[red]Source file not found:[/] {source}")
        raise typer.Exit(1)
    try:
        theme = ThemeSource.model_validate_json(_read_input_bytes(source))
        layout_dict = load_layout(layout)
        keys = compile_theme(theme, layout_dict)
    except (ValueError, ValidationError, OSError) as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1) from None

    out_json = json.dumps([k.model_dump() for k in keys], indent=2) + "\n"
    if output is None or _is_stdio(output):
        # Plain stdout, not rich UI: this is machine-readable JSON for a pipe.
        print(out_json, end="")  # noqa: T201
    else:
        _ = output.write_text(out_json, encoding="utf-8")
        console.print(f"[green]Compiled theme written to:[/] {output}")


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
