# AK820 Pro USB HID Protocol

> Per-command analysis lives in
> [`firmware-analysis-helpers.md`](firmware-analysis-helpers.md);
> Windows-side reverse-engineering of the vendor tool lives in
> [`windows-driver-analysis.md`](windows-driver-analysis.md).
> See [`STATUS.md`](STATUS.md) for the canonical state of findings and
> [`unknown-commands.md`](unknown-commands.md) for the per-CMD analysis of
> debug/internal-test surface.

## Communication Architecture

The keyboard exposes **4 USB HID interfaces**:

| Interface | Usage Page | Purpose |
|-----------|-----------|---------|
| 0 | Standard | Boot keyboard HID |
| 1 | Standard | Consumer control (media keys) |
| 2 | `0xFF68` | Display/data channel (interrupt OUT for LCD image upload) |
| 3 | `0xFF13` | **Command channel** (HID feature reports, 64 bytes) |

All configuration commands go through **Interface 3** using HID feature reports.

## General Packet Format

All packets are **64 bytes**. Structure varies by command type.

### Command Wrapper

For most commands, byte structure is:
- Byte 0: Report ID `0x04`
- Byte 1: Command code
- Bytes 2-61: Command-specific payload
- Bytes 62-63: Delimiter magic bytes `0xAA, 0x55` (for certain commands)

### Handshake Requirement

After sending a `SET_REPORT` (feature report with ID `0x04`), the device firmware requires a `GET_REPORT` to advance its internal state machine. This is critical - skipping the GET_REPORT will cause commands to be ignored.

### Inter-Command Delay

**35ms minimum** between packets to prevent firmware packet loss.

## Command Codes (Host -> Device)

| Code | Purpose | Notes |
|------|---------|-------|
| `0x18` | Session START | Must be sent before any configuration |
| `0xF0` | Session FINISH/END | Sent after configuration is complete |
| `0x02` | Save/commit to flash | Persists changes to EEPROM |
| `0x05` | READ_ID | Returns firmware version + capabilities |
| `0x13` | Lighting mode config | Also writes flash at 0x9800 |
| `0x17` | Sleep timer setting | |
| `0x28` | **Time synchronization** | See time sync format below |
| `0x72` | Image/animation transfer init | LCD screen |
| `0x22` | Read custom per-key colors | From flash 0x9C00 |
| `0x23` | Upload custom per-key RGB data | Writes flash at 0x9C00 |
| `0xF5` | Read live per-key RGB state | |
| `0x11` | **Default-layer keymap upload** | V1.13: writes flash at 0x9400. V1.28+: no-op. |
| `0x15` | Read current keymap | 49 chunks × 64 B |
| `0x20` | Custom-lighting palette upload preamble | Sets state byte = 0x32 |
| `0x27` | **Alternate-layer keymap upload** | Writes flash at 0xAC00 |

Other CMDs (`0x10`, `0x14`, `0x16`, `0x19`, `0x26`, `0x38`, `0xAB`, `0xE0`) exist
in the firmware dispatch but the vendor Windows tool never sends them; treat as
debug/internal-test surface. See [`unknown-commands.md`](unknown-commands.md)
for the per-CMD analysis.

### Typical Command Sequence

```
START (0x18) -> command packet(s) -> SAVE (0x02) -> FINISH (0xF0)
```

## Time Synchronization Packet (Command `0x28`)

This is how the clock on the LCD display gets set.

**64-byte packet structure:**

| Byte | Value | Description |
|------|-------|-------------|
| 0 | `0x04` | Report ID |
| 1 | `0x28` | Command: time sync |
| 2 | `0x00` | Padding |
| 3 | `0x01` | Padding |
| 4 | `0x5A` | Magic marker |
| 5 | year - 2000 | Year offset (e.g., 25 for 2025) |
| 6 | month | 1-12 |
| 7 | day | 1-31 |
| 8 | hour | 0-23 |
| 9 | minute | 0-59 |
| 10 | second | 0-59 |
| 11 | `0x00` | Padding |
| 12 | `0x04` | Fixed value |
| 13-61 | `0x00` | Padding |
| 62 | `0xAA` | Delimiter |
| 63 | `0x55` | Delimiter |

**Example: Setting time to 2025-03-15 14:30:45**

```
04 28 00 01 5A 19 03 0F 0E 1E 2D 00 04 00...00 AA 55
```

## Lighting Mode Packet (Command `0x13`)

**64-byte packet:**

| Byte | Value | Description |
|------|-------|-------------|
| 0 | `0x04` | Report ID |
| 1 | `0x13` | Command: lighting mode |
| 2 | mode | Mode value (0x00-0x13 for presets, 0x80 for custom) |
| 3-5 | R, G, B | Color (0-255 each) |
| 6-9 | `0x00` | Padding |
| 10 | rainbow | 0 = off, 1 = rainbow mode |
| 11 | brightness | 0-5 |
| 12 | speed | 0-5 |
| 13 | direction | 0=left, 1=down, 2=up, 3=right |
| 14-15 | `0x00` | Padding |
| 16-17 | `0x55, 0xAA` | Delimiters |
| 18-63 | `0x00` | Padding |

### Lighting Mode Values

| Value | Mode |
|-------|------|
| `0x00` | Off |
| `0x01` | Static |
| `0x02` | SingleOn |
| `0x03` | SingleOff |
| `0x04` | Glittering |
| `0x05` | Falling |
| `0x06` | Colourful |
| `0x07` | Breath |
| `0x08` | Spectrum |
| `0x09` | Outward |
| `0x0A` | Scrolling |
| `0x0B` | Rolling |
| `0x0C` | Rotating |
| `0x0D` | Explode |
| `0x0E` | Launch |
| `0x0F` | Ripples |
| `0x10` | Flowing |
| `0x11` | Pulsating |
| `0x12` | Tilt |
| `0x13` | Shuttle |
| `0x80` | Per-key custom RGB |

## Sleep Timer Packet (Command `0x17`)

| Byte | Value | Description |
|------|-------|-------------|
| 0 | `0x04` | Report ID |
| 1 | `0x17` | Command: sleep timer |
| 2 | value | 0=never, 1=1min, 2=5min, 3=30min |
| 3-61 | `0x00` | Padding |
| 62 | `0xAA` | Delimiter |
| 63 | `0x55` | Delimiter |

## LCD Image Upload

- **Resolution:** 128x128 pixels
- **Color format:** RGB565, little-endian (2 bytes/pixel)
- **Total data:** 32,768 bytes
- **Transfer interface:** Interface 2 (Usage Page `0xFF68`)
- **Chunk size on the wire:** 4,**123** bytes per chunk (4096 payload + 27-byte
  trailer). Each chunk is split into 64-byte interrupt writes; the trailer
  creates a short final packet that signals the chunk boundary.
- **Chunks:** 9 total
- **Header:** 256-byte GIF header prepended (frame count, timing)
- **Animation:** Up to 141 frames supported
- **Acknowledgement:** Each chunk acknowledged by device (300ms timeout)
- **Initiation:** Send command `0x72` on Interface 3 first, then transfer data on Interface 2

(Earlier revisions of this doc said 4,096 bytes per chunk — that was the
payload, not the wire-level chunk size.)

## Keymap Upload

Per [`windows-driver-analysis.md`](windows-driver-analysis.md): the vendor
Windows tool uploads keymaps via two CMDs depending on layer:

| Layer | CMD | Flash address (V1.13) |
|-------|-----|------------------------|
| 0 (default / fn_layer 0) | `0x11` | `0x9400` (V1.13 only — no-op on V1.28+) |
| 1+ (alternate / custom) | `0x27` | `0xAC00` |

Sequence: `START (0x18) → 0x11 or 0x27 → 9 chunks × 64 B of per-key HID usage
codes → SAVE (0x02) → FINISH (0xF0)`. Per-key encoding is 4 bytes per slot:
`[type_tag, usage_low, usage_high, modifier]`. Type tags include
`1` = HID keyboard, `2` = mouse, `3` = modifier, `6` = consumer/media, `7` = mouse
button/wheel.

## VIA-mode variant

The AK820 Pro family also ships a separate USB identity:

| VID | PID | Mode |
|-----|-----|------|
| `0x0C45` | `0x8009` | Proprietary (this document) |
| `0x3151` | `0x4021` | VIA-compatible (`id_dynamic_keymap_*` over report ID `0x04`) |

How to switch firmware modes is unknown. The proprietary identity is the
default out-of-box and the only one this document covers in detail.

## Per-Key Custom RGB (Command `0x23`)

- Mode `0x80` enables per-key custom colors
- 144 keys addressable
- Each key: position index + R, G, B (4 bytes per key)
- Total payload: 576 bytes, sent in multiple 64-byte packets

## Firmware Version / Device Info Query (Command `0x05` READ_ID)

The READ_ID command (`0x05`) returns a fixed 64-byte response carrying
device identity + firmware version. After discarding the ACK that
follows any SET_REPORT:

| Bytes | Field |
|-------|-------|
| 1-2 | Capabilities (LE uint16, e.g. `0x3040`) |
| 3-4 | Reserved |
| 5-6 | USB VID (little-endian) |
| 7-8 | USB PID (little-endian) |
| 9-10 | **Firmware version** (LE uint16, encoded as `major << 8 \| minor`) |
| 11-12 | End marker (`0xFFFF`) |

So a live device reporting `bcdDevice 1.14` returns bytes 9-10 = `0x0E 0x01`
(i.e. version `0x010E` = 1.14).

Earlier revisions of this file claimed Command `0x01` returns a
"major.minor.patch" triple at bytes 2-4. That was wrong on both axes —
the command is `0x05` and the version is a 16-bit field, not a 3-byte
triple. The ak820ctl decoder lives in `commands.py::get_device_info`.

## 2.4G Dongle Protocol

The 2.4G wireless dongle uses HID page `0xFF60`:
- **Status packet header:** `0x05 0xA6`
- **Connect:** state byte = `0x01`
- **Disconnect:** state byte = `0x02`
- **Keep-alive:** Ping/pong mechanism on the same HID page

## Notes on Bluetooth

Communication over Bluetooth uses the same HID protocol but the interface enumeration may differ. USB wired mode is recommended for configuration as it provides direct access to all 4 HID interfaces.

## References

- TaxMachine/ajazz-keyboard-software-linux - Original C++ RE
- gohv/EPOMAKER-Ajazz-AK820-Pro - Rust implementation
- dantje/ajazz-ak35i-v3-max/PROTOCOL.md - Most detailed protocol docs (same PID)
- fpb/ajazz-ak820-pro - Hardware teardown + pinouts
