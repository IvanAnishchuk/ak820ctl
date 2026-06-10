# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `theme-compile` subcommand: compile high-level theme source JSON
  (`base` + `groups` + `overrides`) into the 144-slot per-key JSON consumed
  by `perkey --load`. Bundled at `src/ak820ctl/data/` via hatchling and
  resolved at runtime through `importlib.resources`.
- 14 bundled theme sources: `groups-{basic,alt,solarized,nord,gruvbox,dracula,cyberpunk,monokai,rainbow}` and `rows-{pastel-turquoise,pastel-sunset,pastel-ocean,pastel-forest,stealth}`
- 2 bundled layouts: `simple.json` (8 semantic groups) and `perrow.json`
  (16 per-row groups)
- Pre-compiled per-key outputs for every shipped theme in `examples/perkey/`
- 14 matching 128×128 LCD smiley PNGs in `examples/lcd/`
- `Key(StrEnum)` enum with 144 named slots (`src/ak820ctl/keys.py`) and
  `KEY_INDEX` mapping built at import time from `data/keymap.json` with a
  drift guard
- `idx_<N>` placeholder names for the slots without a physical key, so
  every one of the 144 LEDs is addressable from theme `overrides`
  (rainbow buffer gaps, firmware-locked underglow slots 128–143)
- `HexColor` strict pydantic type (`#RRGGBB` only, leading `#` required)
  and `ThemeSource` pydantic model
- Stdin/stdout via `-`: `perkey --load -`, `perkey --save -`, and
  `theme-compile [-o] -` follow the conventional Unix dash sentinel, so
  `theme-compile <src> | perkey --load -` works without `/dev/stdin`
- `scripts/demo_themes.py`: cycle every shipped theme + matching LCD
  image on the connected keyboard with a 10 s interval per theme
- `scripts/generate_smileys.py`: regenerate `examples/lcd/*.png` from the
  in-script expression table
- `docs/PROTOCOL.md`, `docs/RESEARCH.md`, `docs/FIRMWARE-HACKING.md`:
  vendored protocol/research references (366 lines total) so CI and
  agents have the wire-format reference and cross-developer context in-tree
- `pyrightconfig.json`: shared venv discovery (`venvPath`, `venv`,
  `pythonVersion`, `extraPaths`, `include`) so vanilla pyright (used by
  IDE/LSP integrations) and basedpyright read one source of truth
- `image` / `gif` commands: upload static images and animated GIFs to the 128×128 LCD screen
- `perkey` command: read and set per-key custom RGB colors for 144 keys
  - `--save`/`--load` for round-trip JSON persistence of per-key color configs
  - `--dump`/`--dump-stored` for stdout inspection of live/flash state
  - `--all`, `--key INDEX:RRGGBB` for quick color changes
  - LED index keymap: 81 physical keys mapped out of 144 LED positions
  - Example color schemes: groups, rainbow, blocks, ocean, sunset, stealth
- `dump` / `restore` commands: save and load keyboard settings as JSON
- Pydantic models for typed serialization/validation of keyboard settings
- `light --show` / `light` (no args): read and display current lighting config from keyboard
- `info` command: show device VID/PID and capabilities from CMD 0x05 response
- `send_report()`, `read_data()` HID helpers for read operations
- CLI commands: `time`, `light`, `sleep`, `info`
- USB HID protocol implementation for Ajazz AK820 (VID 0x0C45, PID 0x8009)
- Time sync, LED mode control (20 presets + custom), sleep timer
- Type stubs for hidapi C extension
- Hypothesis property-based tests for protocol packets
- Meson/ninja build orchestration (10 targets)
- Three type checkers: ty, mypy (strict), basedpyright (recommended)
- Mutation testing support (mutmut)
- Modular CI workflows with hardened runners and pinned action SHAs
- Security scaffolding: CodeQL, Scorecard, OSV scan, gitleaks, dependency review
- Supply-chain audit script (pip-audit + CycloneDX SBOM)
- Dependabot config (uv, pre-commit, github-actions ecosystems)
- Dependabot regen workflow for requirements*.txt sync
- Protocol documentation: COMMANDS.md, STATUS.md

### Changed

- `ThemeSource` and `KeyboardDump` use plain mutable defaults (`= {}`,
  `= DeviceInfo()`, `= LightingConfig()`) instead of
  `Field(default_factory=...)`; pydantic v2 deep-copies these
  per-instance so behaviour is unchanged. Pinned by new
  `tests/test_models.py`. Drops `models.py` mypy explicit-Any from
  288 → 204 and omitted-generics from 101 → 45.
- meson `mypy-strict` ninja target now emits every mypy report format
  (any-exprs, lineprecision, linecount, linecoverage, html, txt, xml,
  cobertura, junit, jsonl) alongside the pass/fail log. `lxml` and
  `lxml-stubs` added as dev dependencies to enable
  `--cobertura-xml-report`.
- `data/keymap.json`: digit names `"1".."0"` renamed to `digit_1..digit_0`
  so they're valid Python identifiers for the `Key` enum
- `data/keymap.json`: previously-`null` slots renamed to stable
  `idx_<N>` placeholders so they remain addressable from theme `overrides`
- `ThemeSource.overrides` typed as `dict[Key, HexColor]` (was
  `dict[str, HexColor]`); unknown key names now fail at parse time with
  a pydantic `ValidationError` citing the bad name
- Removed `ThemeSource.indices` field — covered by `overrides` now that
  every slot has a name
- Renamed CLI helpers `_parse_hex_color`, `_parse_key_spec`,
  `_compile_theme`, `_load_layout` to drop the leading underscore; they're
  stateless utilities tested from outside the module
- Renamed `display._rgb565_pixel` to `display.rgb565_pixel` for the same
  reason (stateless RGB565 pixel encoder, tested externally)
- `perkey --key INDEX:RRGGBB` validates all specs before reading device
  state, so a malformed spec fails fast without making a device round-trip
- meson `requirements` ninja target uses `--output-file <relative>` so
  the embedded `uv export` header matches `scripts/regen_requirements.py`
  and `.github/workflows/dependabot-regen.yml` byte-for-byte
- `info` command: use CMD 0x05 for full device ID with LE uint16 firmware version (shows V1.20)

### Fixed

- LCD `upload_image` was leaving the device session state machine open
  (sequence was START → image-chunks → SAVE without END), so the next
  command on Interface 3 — e.g. a subsequent `perkey --load` — was
  silently dropped and the keyboard stayed dark. Added CMD_END with a
  regression test.
- LED color command: split into preamble + data payload (two-packet sequence)
- Replaced broad `except Exception` with specific `OSError` for HID errors
- Fixed firmware version display (`info` command)
- Eliminated double inter-command delay in `send_command()` (was sleeping in both `send_report()` and `send_command()`)
- Dependabot regen workflow trigger paths
- `scripts/regen_requirements.py`: pass `--output-file` explicitly so the
  header matches CI (also covered by the meson alignment above)
