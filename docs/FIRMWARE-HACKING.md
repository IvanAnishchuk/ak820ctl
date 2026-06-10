# AK820 Pro Firmware Hacking

> For Phase 1 helper-function semantics (flash I/O, buffer management,
> chunk handling, LED modes) see
> [`firmware-analysis-helpers.md`](firmware-analysis-helpers.md). For the
> canonical Phase 1–4 status and the per-CMD discoveries see
> [`STATUS.md`](STATUS.md) and [`unknown-commands.md`](unknown-commands.md).
> Full firmware-disassembly working files (V1.13 binary, per-blob diffs,
> Ghidra projects, dispatch extractor) live out-of-tree in the
> `ak820-experiments/ak820-re/` reverse-engineering repo.

## Chipset Details

The AK820 Pro uses a **Sonix SN32F299** (branded as HFD80CP100) ARM Cortex-M MCU. This is the same chip family used across many budget/mid-range mechanical keyboards.

## Bootloader Entry

1. Remove keycaps around spacebar area
2. Locate two pads under the spacebar (covered by 2 insulation layers + 1 removable foam strip)
3. Short these two pads together
4. While shorted, plug in USB cable
5. Device will enumerate with VID `0x0C45` / PID `0x7140` (bootloader mode)
6. Release the short

## Stock Firmware

The `fpb/ajazz-ak820-pro` repo contains stock firmware binaries for 8 family
members:

| Blob | Notable handler differences vs V1.13 |
|------|--------------------------------------|
| `AJAZZ_AK820PRO_..._V1.13_...bin` | The "reference" — only firmware with `cmd_0x11 → flash@0x9400` and `cmd_0x19` (BT-flag set) in its dispatch |
| `JAMESDONKEY_RS2_3.0_..._V1.28_...bin` | Newest blob, same shape as V1.13 except no `cmd_0x11` flash write |
| `LANGTU_LT84_..._V1.03_...bin`, `LEOBOD_K81PRO_..._V1.09_...bin`, `QK75N_..._V1.13_...bin`, `WOMIER_..._V1.01_...bin`, `HELLOGANSS_XS75T_..._V1.41_...bin`, `HELLOGANSS_XS75T_..._V1.42_...bin` | Same command set as V1.13, varying flash code layouts |

For the per-CMD address matrix across all 8 blobs and the divergence
narrative, see the working files in the `ak820-re/` reverse-engineering
repo (`firmware-blobs/diff.md`,
`firmware-blobs/cross-firmware-divergences.md`).

## Dispatch architecture

The vendor firmware uses **two separate dispatch chains**, not a single
fall-through. They are two independent state machines:

- **First dispatch** (`h_61c8_dispatcher` @ V1.13 `0x61C8`): runs on host
  SET_REPORT. The write-side / immediate-action half. CMDs that write flash
  (`0x11` keymap default, `0x13` lighting, `0x23` per-key RGB, `0x27` keymap
  alt) call `h_18002_flash_io(<region>)` here.
- **Second dispatch** (separate function at V1.13 `0x645E`): runs as the
  GET_REPORT response producer. The read-side. Read CMDs (`0x10`, `0x12`,
  `0x14`, `0x15`, `0x16`, `0x22`, `0x26`, `0xF5`) queue a buffer via
  `h_6190(buf, off, count)` here for the next outbound chunks.

A CMD can live in both chains, one, or neither. The Phase 2 extractor
script in the `ak820-re/` repo (`extract_dispatch.py`) finds both chains
by pattern.

## Flash region map (V1.13)

| Address | Written by | Purpose |
|---------|-----------|---------|
| `0x9400` | `cmd_0x11` (V1.13 only) | Default-layer keymap |
| `0x9800` | `cmd_0x13 SET_LIGHTING` | Lighting mode persistence |
| `0x9C00` | `cmd_0x23 WRITE_PERKEY` | Per-key RGB palette |
| `0xAC00` | `cmd_0x27` | Alternate-layer keymap (and possibly other config) |

## Firmware Dump

Using ST-Link debugger + `SonixQMK/sonix_dumper`:
- Can dump the entire flash contents
- Useful for backup before flashing anything custom
- Can also use the bootloader mode for dumping

## QMK Port Status

**Not yet available.** The SN32F299 is not currently supported in SonixQMK (only F248/F248B/F268). However:
- The hardware documentation exists (key matrix pinout, LED matrix pinout)
- The bootloader is accessible
- The SonixQMK infrastructure (flasher, bootloader tools) exists for the chip family
- Someone just needs to add SN32F299 support + AK820 keymap/config

## Fun Hacking Possibilities

### LCD Screen Hacking
- 128x128 TFT LCD with GC9107 controller
- Connected via SPI to main MCU
- Can upload custom images/animations (up to 141+ frames)
- RGB565 format, no DRM or signing
- **Idea:** System stats display (CPU temp, RAM usage), custom animations, clock faces

### Custom Firmware Ideas
- Full QMK port would give: layers, tap-dance, combos, leader key, mouse keys
- ZMK port exists for the Max HE variant (hardware mod required)
- ESP32 replacement project exists (full MCU swap for BLE)

### Wireless Protocol Hacking
- BT module is WCH CH582F with documented I2C wiring
- 2.4G dongle protocol partially documented
- Could potentially modify BT behavior or add custom wireless features

### Key Matrix
```
6 rows x 15 columns
Row pins: PA8, PA9, PA10, PA11, PA12, PA13
Col pins: PB0-PB14
```

### LED Matrix
- Row pins via NPN transistors
- Column pins via PNP transistors
- Per-key RGB addressable (144 keys)

## Related Keyboard Firmware (Same Chipset)

These keyboards use compatible Sonix chips and may have portable code:
- Helloganss XS75T
- JamesDonkey RS2
- Langtu LT84
- Leobod K81 Pro
- QK75N
- Womier S-K80

## Tools

| Tool | URL | Purpose |
|------|-----|---------|
| SonixQMK Flasher | https://github.com/SonixQMK/sonix-flasher | Flash firmware via bootloader |
| Sonix Dumper | https://github.com/SonixQMK/sonix_dumper | Dump firmware via ST-Link |
| SonixQMK | https://github.com/SonixQMK/qmk_firmware | QMK fork for Sonix chips |
| SonixQMK Docs | https://sonixqmk.github.io/SonixDocs/ | Documentation |

## Safety Notes

- **Always dump stock firmware first** before flashing anything
- The bootloader itself should be safe - it's ROM-based and can't be bricked by bad firmware
- However, flashing incompatible firmware could make the keyboard non-functional until re-flashed
- The 16MB SPI flash (PY25Q128HA) stores settings/animations, separate from MCU firmware
