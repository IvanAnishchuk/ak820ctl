# CLAUDE.md

## Project Overview

ak820ctl -- Linux CLI tool for controlling Ajazz AK820 keyboard (time, LED, sleep)

CLI tool built with typer + rich + hidapi. Source layout under `src/ak820ctl/`.
Communicates via USB HID feature reports on Interface 3 (Usage Page 0xFF13).
Protocol reverse-engineered from Wireshark captures of the Windows driver.

## Commands

```bash
# Install dependencies
uv sync

# Run the CLI
uv run ak820ctl --help

# Run tests with coverage
uv run pytest

# Lint + format
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/

# Type check
uv run ty check

# Full pre-commit suite
uv run pre-commit run --all-files

# Supply-chain audit (pip-audit + SBOM)
uv run python scripts/audit.py
```

## CLI subcommands

Top-level: `time`, `light`, `sleep`, `info`, `dump`, `perkey`, `theme-compile`, `image`, `gif`, `restore`.

### `time` — sync the keyboard clock

- No args: sets to current system time.
- `--set "YYYY-MM-DD HH:MM:SS"` / `-s` — set explicit time. Also accepts `HH:MM:SS` and `HH:MM`
  (date defaults to today) and `YYYY-MM-DD HH:MM`.

### `light` — global lighting mode

- Positional `MODE` — one of: `off`, `static`, `breath`, `spectrum`, `ripples`, `flowing`,
  `glittering`, `falling`, `colourful`, `outward`, `scrolling`, `rolling`, `rotating`, `explode`,
  `launch`, `pulsating`, `tilt`, `shuttle`, `single-on`, `single-off`, `custom`.
- `--color RRGGBB` / `-c` (default `ff0000`); `--brightness 0-5` / `-b`; `--speed 0-5` / `-S`;
  `--direction left|right|up|down` / `-d`; `--rainbow` / `-r`.
- `--show` / `-s` — read current config instead of writing. No-arg `light` also shows.
- `custom` mode is what `perkey` writes into; switch to it before per-key colors are visible.

### `sleep` — sleep timer

- Positional `TIMEOUT`: `never` (default), `1min`, `5min`, `30min`.

### `info` — show VID/PID, device path, firmware version.

### `dump` — full settings snapshot to JSON

- `--output PATH` / `-o` — write to file; default stdout. Pair with `restore`.

### `restore` — apply a `dump` JSON

- Positional `INPUT_FILE` — JSON produced by `dump`.
- `--skip-time` — leave the clock alone.

### `perkey` — per-key RGB (144 keys)

- `--dump` / `-d` — print live per-key state as JSON to stdout (requires connected keyboard).
- `--dump-stored` — print stored-in-flash state as JSON.
- `--save PATH` / `-s` — save live state to a JSON file. `-` for stdout.
- `--load PATH` / `-l` — load colors from a JSON file and write them. `-` for stdin.
- `--all RRGGBB` / `-a` — set every key to one color.
- `--key INDEX:RRGGBB` / `-k` — set one key by index (repeatable).
- `--brightness 0-5` / `-b` — brightness for write ops (default 5).
- No args: shows live state in a TTY view.

Per-key colors are only visible while global lighting `mode` is `custom`
(`ak820ctl light custom`). Other modes ignore the per-key buffer.

JSON format: list of `{"index": int, "r": int, "g": int, "b": int}` for indices 0-143.

### `theme-compile` — compile a theme source to per-key JSON

- Arg: theme source JSON path (`-` for stdin).
- `--layout PATH` — layout JSON (default: bundled `simple.json`; use `perrow.json` for `rows-*` themes).
- `--output PATH` / `-o` — write to file (default: stdout, `-` is also stdout).
- Theme source format: `{base, groups: {group→hex}, overrides: {Key→hex}}`. See `src/ak820ctl/data/README.md`.

### `image` — upload a static image to the LCD

- Arg: image file (PNG/JPG/BMP/etc.; PIL-supported).
- `--slot INT` / `-s` — LCD slot index (default `1`, max `255`).
- Image is resized to **128×128** with NEAREST resampling, converted to RGB565-LE.
- Replaces the firmware status screen; only way back is the wheel button or a different `image`/`gif` call.

### `gif` — upload an animated GIF to the LCD

- Arg: GIF file. Up to **141 frames**; same 128×128 RGB565 format as `image`.
- Same `--slot` option as `image`.

### Key enum

`src/ak820ctl/keys.py` defines `Key(StrEnum)` with 144 members (one per LED slot, in slot-index
order). `KEY_INDEX: dict[Key, int]` is built at import from `src/ak820ctl/data/keymap.json` and
guarded against drift. Slots without a physical key are named `idx_<N>` (e.g. `idx_0`, `idx_14`,
... `idx_143`) so every slot is addressable from `Key` and from theme `overrides`. The keymap
JSON is no longer user-overridable at runtime.

## Repo layout

- `src/ak820ctl/data/themes/` — 14 bundled theme **sources** (`*-theme.json`). See catalog below.
- `src/ak820ctl/data/layouts/` — `simple.json` (8 semantic groups) and `perrow.json` (16 per-row groups).
- `src/ak820ctl/data/keymap.json` — index→Key-name map (read by `keys.py`, not user-editable).
- `src/ak820ctl/data/README.md` — full theme-source format reference.
- `examples/perkey/*.json` — pre-compiled outputs (one per shipped theme). Used as fixtures by the
  byte-identical regen test, so any theme/layout/keymap edit may require regenerating these.
- `examples/lcd/*.png` — matching 128×128 LCD smileys per theme, plus `animation.gif`.
- `docs/PROTOCOL.md` — wire format for every HID command (read this before editing `hid.py` or
  `commands.py`).
- `docs/RESEARCH.md` — chipset, related-project list, official software pointers.
- `docs/FIRMWARE-HACKING.md` — bootloader/MCU notes (out of CLI scope but useful background).

## Bundled themes

| Theme | Layout |
|---|---|
| `groups-{basic,alt,solarized,nord,gruvbox,dracula,cyberpunk,monokai,rainbow}` | `simple.json` (default) |
| `rows-{pastel-turquoise,pastel-sunset,pastel-ocean,pastel-forest,stealth}` | `perrow.json` (must pass `--layout`) |

## Common workflows

```bash
# Apply a bundled theme — pipe stdin/stdout via `-`
uv run ak820ctl theme-compile src/ak820ctl/data/themes/groups-dracula-theme.json \
  | uv run ak820ctl perkey --load -

# Same, for a rows-* theme (different layout)
uv run ak820ctl theme-compile src/ak820ctl/data/themes/rows-stealth-theme.json \
  --layout src/ak820ctl/data/layouts/perrow.json \
  | uv run ak820ctl perkey --load -

# Per-key colors only show when global mode is `custom`
uv run ak820ctl light custom

# Snapshot + restore full keyboard state
uv run ak820ctl dump -o backup.json
uv run ak820ctl restore backup.json

# Cycle every shipped theme on the LCD + keys (10s each, requires connected device)
uv run python scripts/demo_themes.py
```

## Scripts

- `scripts/demo_themes.py` — walks `examples/perkey/*.json` + matching `examples/lcd/*.png`,
  uploads the LCD image and writes the per-key colors with a 10s interval per theme.
- `scripts/generate_smileys.py` — regenerates `examples/lcd/*.png` from the in-script theme
  expression table. Run after adding/changing a shipped theme.
- `scripts/audit.py`, `scripts/regen_requirements.py` — supply-chain + lockfile maintenance.

## Protocol gotchas

- HID command channel: **Interface 3, Usage Page 0xFF13, 64-byte feature reports.** Every
  `SET_REPORT` must be followed by a `GET_REPORT` to advance the device state machine — see
  `hid.py::send_command`.
- LCD upload sequence: **START (0x18) → image-chunks → SAVE (0x02) → END (0xF0).** Omitting END
  leaves the session open; the next command (e.g. a subsequent `perkey --load`) is silently
  dropped. See `display.py::upload_image` and `perkey.py`.
- Per-key colors are only visible while global `light` mode is `custom` (`0x80`). Other modes
  ignore the per-key buffer.
- Inter-command delay: 35 ms minimum to prevent firmware packet loss (`FW_DELAY` in `hid.py`).

## Out-of-scope / future-epic notes

These are surfaced by neighbouring projects (see `docs/RESEARCH.md`) and not yet implemented
here — flag them when relevant, don't silently implement during unrelated work:

- **udev rule.** `epomaker-ak820-pro` ships a `99-ak820.rules` so non-root users can talk to
  hidraw. We don't. Easy pick when packaging.
- **2.4G dongle / Bluetooth.** Documented in `docs/PROTOCOL.md`; ak820ctl is USB-wired only.
- **Auto-switch hooks on connect/disconnect** (mrworldwide-rs has this).
- **GUI front-end.** Out of scope; CLI-only by design.
- **QMK port / custom firmware.** See `docs/FIRMWARE-HACKING.md`; nothing for this repo to do
  until SN32F299 lands in SonixQMK.

## Conventions

- Python 3.14+, src layout, hatchling build backend
- Ruff for linting (line-length 100, security rules enabled) and formatting
- ty for type checking
- pytest with coverage (threshold in pyproject.toml)
- Conventional commits enforced by pre-commit hook
- All CI checks must pass before merge (see .github/workflows/ci.yml)
- Never squash merge PRs — use merge commits to preserve commit history
- Never use `git add -A` or `git add .` — always stage individual files by name
