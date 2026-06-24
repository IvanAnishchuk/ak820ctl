# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `scripts/demo_all.sh`: end-to-end hardware demo walking the full CLI
  surface (`info`, `time`, `sleep`, global `light` modes, custom per-key
  LED themes via `theme-compile | perkey --load`, and LCD `image`/`gif`
  upload). Snapshots lighting + per-key state up front and restores it on
  exit (EXIT trap). Tunable via `PAUSE` / `BACKUP_DIR` / `SLOT` env vars.
  Warns before the irreversible LCD-slot overwrite and flags the two
  mutations it can't restore (sleep timer, LCD slot — the protocol has no
  read-back). A first-class `demo` subcommand is tracked in #61.
- `probe` subcommand: send safe read-only CMDs and print response
  shapes. `--cmd HEX` runs a single opcode against the whitelist
  (0x05 / 0x10 / 0x12 / 0x14 / 0x15 / 0x16 / 0x26 / 0xE0);
  `--all` runs the whole whitelist; `--output-dir PATH` dumps raw
  responses to one file per opcode. Refuses destructive opcodes
  (0x11 / 0x13 / 0x23 / 0x27 / 0x38) with a clear error pointing at
  the write surface (Tier E). Useful for live verification of
  canonical findings without leaving the project.
- `keymap` subcommand: reads the stored keymap buffer via CMD 0x15
  (49 chunks x 64 bytes = 3,136 raw bytes). `keymap --dump` writes
  `{"size", "hex"}` JSON to stdout; `keymap --save PATH` writes the
  same to a file (`-` is stdout). Per-slot decoding
  (`[type_tag, usage_low, usage_high, modifier]`) and the keymap
  write path (CMDs 0x11 / 0x27) are not yet exposed — see plan2.md
  Tier E. New `src/ak820ctl/keymap.py` module exposes
  `read_keymap`, `parse_keymap_data`, `NUM_KEYMAP_CHUNKS`,
  `KEYMAP_BYTES`.
- `stubs/typer/__init__.pyi` — vendored type stubs for the typer surface
  used by `ak820ctl.cli` (`Typer`, `Option`, `Argument`, `Exit`,
  `command`/`callback` decorators). Drops mypy explicit-Any in `cli.py`
  from 267 → 234 and `__main__.py` from 1 → 0.
- meson `diff-cover-mypy` ninja target: per-PR mypy type-precision
  gating against `${DIFF_BASE:-origin/main}` using the
  `mypy-strict-cobertura/cobertura.xml` cobertura report. Mirrors the
  test-coverage `diff-cover` flow and emits both JSON and markdown.
  `diff-cover` added as a dev dependency.
- meson `mypy-paranoid` ninja target: same 11 reports as `mypy-strict`
  but with `--disallow-any-explicit / -decorated / -unimported`,
  `--warn-unreachable`, `--strict-bytes`, and
  `--strict-equality-for-none` enabled. Allowed to fail; the value is
  surfacing framework-imposed `Any` (typer/pydantic) separately from
  real debt at a glance.
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

- Named command opcodes are now exported as module-level constants
  instead of bare hex literals. `commands.py` gains `CMD_READ_ID`,
  `CMD_READ_LIGHTING`, `CMD_SET_LIGHTING`, `CMD_SET_SLEEP`,
  `CMD_SET_TIME` and (future-only, not yet wired)
  `CMD_KEYMAP_DEFAULT`, `CMD_READ_KEYMAP`,
  `CMD_CUSTOM_LIGHTING_PREAMBLE`, `CMD_KEYMAP_ALT`. `hid.py` gains
  `CMD_START`, `CMD_SAVE`, `CMD_END` (used by the session helpers) and
  `VIA_VID`/`VIA_PID` for the VIA-mode hint. No behaviour change.
- `commands.set_lighting` docstring now notes that CMD 0x13 persists
  the lighting config to flash at 0x9800 — there is no transient-only
  variant.
- `hid.find_device` error message extended to mention the VIA-mode
  dual identity (VID `0x3151` / PID `0x4021`) so a confused user sees
  why their device enumerates without matching `0x0C45/0x8009`.
- `display.upload_image` stale comment "Output report: report ID 0x00
  + 4096 bytes data" rewritten to explain the wire-format relationship
  to the canonical 4123-byte chunk and to record that the canonical
  form was tried live on V1.14 firmware and produced garbled output
  (every retry, both `image` and `gif` paths). The 4097-byte
  short-packet form is what we actually send; the trailer constants
  in `hid.py` (`DISPLAY_TRAILER_SIZE` / `DISPLAY_CHUNK_WIRE_SIZE`)
  are commented out as future-debugging breadcrumbs.
- `types-Pillow` added as a dev dependency; the
  `# pyright: ignore[reportUnknownMemberType]` and explanatory comment
  on `display.frame_to_rgb565` are removed (Pillow's stubs cover
  `Image.resize` now). Drops `display.py` mypy explicit-Any from
  33 → 26 and unimported-Any from 1 → 0.
- Explicit `dict[int, str]` annotations on `commands.LIGHT_MODE_NAMES`
  and `commands.DIRECTION_NAMES` to lock in the reverse-mapping types
  (mypy already inferred them correctly; the annotation guards against
  future drift).
- Vendored docs (`docs/PROTOCOL.md`, `docs/FIRMWARE-HACKING.md`,
  `docs/RESEARCH.md`) re-synced from the canonical
  `ak820-experiments/` umbrella files (canonical LCD chunk size 4123,
  which we later debunked on V1.14 — see the `display.upload_image`
  note above; new CMDs
  `0x05`/`0x11`/`0x15`/`0x20`/`0x27`, `0x13 SET_LIGHTING` flash
  persistence at `0x9800`, VIA-mode dual-identity variant, two-dispatch
  firmware architecture, flash region map, 8-blob firmware family
  table). Newly vendored from `ak820-experiments/ak820-re/`:
  `docs/STATUS.md`, `docs/unknown-commands.md`,
  `docs/firmware-analysis-helpers.md`, `docs/windows-driver-analysis.md`.
  CLAUDE.md repo layout updated to reference the new files; future-epic
  notes gained entries for keymap upload (CMDs `0x11`/`0x27`/`0x15`) and
  the VIA-mode variant.
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
- `info` command: use CMD 0x05 for full device ID with LE uint16 firmware version (shows V1.20)
- `scripts/regen_requirements.py` is now the single requirements exporter,
  with `--stdout` (pipe) and `--output-dir` (files) modes; the meson
  `requirements` target and `release.yml` both call it instead of inlining
  `uv export`.
- `scripts/audit.py` generates requirements ephemerally from `uv.lock` (a temp
  dir) instead of reading committed files; still audits prod and prod+dev
  separately. The release SBOM is now prod-only.
- `.github/settings.yml`: default to merge commits (squash and rebase disabled)
  to match the never-squash policy; per-project overridable.
- Dev tooling bumped (ruff, pytest, pip-audit, meson-python, basedpyright),
  superseding Dependabot PR #59.

### Removed

- Committed `requirements.txt` / `requirements-dev.txt` — `uv.lock` is the
  single source of truth; requirements are generated on demand.
- `.github/workflows/dependabot-regen.yml` — its `GITHUB_TOKEN` push never
  re-triggered CI, so regenerated requirements could land unaudited.
- The `regen-requirements` pre-commit hook (no committed files left to sync).

### Fixed

- `.github/settings.yml`: add `restrictions: null` so the Probot Settings app
  applies the scaffolded branch protection (it silently no-ops without it).
- `hid.read_data` classified packets by position (first read = ACK,
  remaining N = data), so any time stale state sat on the kernel queue
  — common after a state-changing command (light / sleep / time) — the
  caller picked up the echo-of-request bytes instead of real data.
  Symptoms: `ak820ctl info` returning "v0.01" on the second call against
  the same handle, every probe-after-mutation response coming back as
  `[0x04, <cmd>, ...]`. Now classifies by packet shape: drains feature
  reports matching `[REPORT_ID, cmd_byte, 0x00, *, 0x00, 0x00, 0x00, 0x00, ...]`
  as ACK echoes (bounded by `MAX_ACK_DRAINS`) and returns everything
  else as data. `commands.get_device_info` and `commands.read_lighting`
  now also issue `session_save` + `session_end` after the read to flush
  the firmware state machine so the *next* read on the same handle gets
  fresh bytes. All callers (`get_device_info`, `read_lighting`,
  `read_perkey_live`, `read_perkey_stored`, `read_keymap`, `probe_one`)
  updated to pass `cmd_byte` through. Hardware-verified: three back-to-back
  `get_device_info` calls on the same handle all report v1.14; a
  mutate-then-`read_lighting` round-trip on the same handle reflects
  the mutation accurately.
- `commands.get_device_info` firmware-version decoder formatted the
  minor byte as decimal (`:02d`), so byte `0x14` came out as "20" and
  V1.14 firmware reported as "v1.20". Changed to hex format (`:02x`)
  to match the BCD-style convention USB `bcdDevice` uses (0x14 → "14").
  `ak820ctl info` now correctly reports v1.14 on the test device,
  matching `lsusb`. Test fixtures and assertions updated; the helper
  `device_info_packet`'s `fw_minor` default flipped from `20` to
  `0x14` to reduce reader confusion.
- `docs/PROTOCOL.md` "Firmware Version Query" section was preserved
  verbatim from a stale revision of the canonical umbrella — claimed
  CMD `0x01` returns a `major.minor.patch` triple at bytes 2-4. Now
  matches the corrected canonical: CMD `0x05` READ_ID with a 12-byte
  response layout (capabilities, VID, PID, LE-uint16 firmware version,
  end marker). The decoder in `commands.py::get_device_info` was
  always correct; only the doc was stale.
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

### Security

- Bump the dev-only transitive `msgpack` 1.1.2 → 1.2.1 (via `cachecontrol`,
  pulled in by `pip-audit`) to clear advisory GHSA-6v7p-g79w-8964. Runtime
  deps are unaffected; this only touches the audit toolchain.
