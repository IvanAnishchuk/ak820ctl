# AK820 Command Reference & Roadmap

## Transport Layer

- **Interface 3** (Usage Page `0xFF13`): Command channel — 64-byte HID feature reports
- **Interface 2** (Usage Page `0xFF68`): Display data — 4096-byte output reports (image chunks only)
- **35 ms minimum** between all HID operations (firmware silently drops faster commands)
- First `GET_REPORT` after any command is an echo/ACK — discard it

## Implemented Commands

### `time` — Clock Sync (CMD `0x28`)

Syncs system clock to the keyboard's RTC for the LCD display.

```
Sequence: START → CMD_TIME preamble → time data → SAVE
```

**Time data payload (64 bytes):**

| Byte | Field | Value |
|------|-------|-------|
| 0 | marker | `0x00` |
| 1 | slot | `0x01` |
| 2 | magic | `0x5A` |
| 3 | year | year − 2000 |
| 4 | month | 1–12 |
| 5 | day | 1–31 |
| 6 | hour | 0–23 (local time) |
| 7 | minute | 0–59 |
| 8 | second | 0–59 |
| 9 | reserved | `0x00` |
| 10 | fixed | `0x04` |
| 11–61 | padding | `0x00` |
| 62–63 | delimiter | `0xAA 0x55` |

### `light` — Lighting Mode (CMD `0x13`)

Sets one of 20 preset LED modes or activates per-key custom mode.

```
Sequence: START → CMD_LIGHTING preamble → lighting data → SAVE
```

**Lighting data payload (64 bytes):**

| Byte | Field | Range |
|------|-------|-------|
| 0 | mode | `0x00`–`0x13`, `0x80` |
| 1 | R | 0–255 |
| 2 | G | 0–255 |
| 3 | B | 0–255 |
| 4–7 | reserved | `0x00` |
| 8 | rainbow | 0/1 |
| 9 | brightness | 0–5 |
| 10 | speed | 0–5 |
| 11 | direction | 0=left 1=down 2=up 3=right |
| 12–61 | padding | `0x00` |
| 62–63 | delimiter | `0x55 0xAA` |

**Mode values:**

| Hex | Name | Hex | Name |
|-----|------|-----|------|
| `0x00` | off | `0x0A` | scrolling |
| `0x01` | static | `0x0B` | rolling |
| `0x02` | single-on | `0x0C` | rotating |
| `0x03` | single-off | `0x0D` | explode |
| `0x04` | glittering | `0x0E` | launch |
| `0x05` | falling | `0x0F` | ripples |
| `0x06` | colourful | `0x10` | flowing |
| `0x07` | breath | `0x11` | pulsating |
| `0x08` | spectrum | `0x12` | tilt |
| `0x09` | outward | `0x13` | shuttle |
| | | `0x80` | per-key custom |

### `sleep` — Sleep Timer (CMD `0x17`)

Sets the display auto-sleep timeout.

```
Sequence: START → CMD_SLEEP → SAVE
```

| Value | Timeout |
|-------|---------|
| `0x00` | never |
| `0x01` | 1 minute |
| `0x02` | 5 minutes |
| `0x03` | 30 minutes |

### `info` — Device Info (CMD `0x05`)

Queries firmware version and device identity.

```
Sequence: CMD_READ_ID (arg8=0x01) → discard ACK → read 1 data packet
```

**Response payload (after hidapi report ID byte at index 0):**

| Bytes | Field |
|-------|-------|
| 1–2 | capabilities, LE uint16 (`0x3040`) |
| 3–4 | reserved |
| 5–6 | USB VID, little-endian |
| 7–8 | USB PID, little-endian |
| 9–10 | firmware version, LE uint16 (major.minor) |
| 11–12 | end marker (`0xFFFF`) |

### Session Control

| Code | Name | Purpose |
|------|------|---------|
| `0x18` | `CMD_START` | Begin session (arg2=`0x01`) |
| `0x02` | `CMD_SAVE` | Persist to flash |
| `0xF0` | `CMD_FINISH` | End transaction (arg2=`0x01`) |

---

### `light --show` — Read Current Lighting Config (CMD `0x12`)

Reads current lighting mode, color, brightness, speed, direction, and rainbow state.

```
Sequence: CMD_READ_LIGHTING (arg8=0x01) → discard ACK → read 1 data packet
```

**Response payload (after hidapi report ID byte at index 0):**

| Byte | Field |
|------|-------|
| 1 | mode (`0x00`–`0x13`, `0x80`) |
| 2 | R (0–255) |
| 3 | G (0–255) |
| 4 | B (0–255) |
| 5–8 | reserved |
| 9 | rainbow (0/1) |
| 10 | brightness (0–5) |
| 11 | speed (0–5) |
| 12 | direction (0=left 1=down 2=up 3=right) |

---

## Unimplemented Commands

### Per-Key Custom RGB — Write (CMD `0x23`) ⬜

Upload individual colors for each of 144 keys.

```
Sequence: START → CMD_CUSTOM_LIGHT (arg2=0x09) → 9 × 64-byte data packets → SAVE → FINISH
```

Then activate with lighting mode `0x80`.

**Data format:** 144 entries × 4 bytes = 576 bytes across 9 packets.

| Offset | Field |
|--------|-------|
| 0 | key position index (0x00–0x8F) |
| 1 | R |
| 2 | G |
| 3 | B |

**CLI ideas:**
- `ak820ctl perkey --file colors.json` — load from file
- `ak820ctl perkey --key 42 ff0000` — set single key
- `ak820ctl perkey --all 00ff00` — set all keys same color

### Per-Key Custom RGB — Read (CMD `0xF5`) ⬜

Read live per-key RGB state from device.

```
Sequence: CMD_READ_PERKEY (arg2=0x09) → discard ACK → read 9 × 64-byte packets → SAVE → FINISH
```

**CLI ideas:**
- `ak820ctl perkey --dump` — save current per-key state to JSON
- `ak820ctl perkey --dump-stored` — read from flash (CMD `0x22`)

### Read Stored Per-Key Colors (CMD `0x22`) ⬜

Same as `0xF5` but reads from flash instead of live state.

### LCD Image Upload (CMD `0x72`) ✅

Upload static image or animated GIF to the 128×128 (or 240×135) LCD screen.

```
Sequence: START → CMD_IMAGE (slot, chunk_count) → data chunks on Interface 2 → SAVE
```

**Display parameters:**
- Resolution: 128×128 (AK820 Pro) or 240×135 (AK35i V3 MAX variant)
- Pixel format: RGB565, little-endian (2 bytes/pixel)
- Chunk size: 4096 bytes (on Interface 2 via output reports)
- Max frames: 141

**Image header (256 bytes):**

| Byte | Field |
|------|-------|
| 0 | frame count N (1–141) |
| 1..N | per-frame delay in 2ms units (1–255 → 2–510ms) |
| N+1..255 | padding (`0xFF`) |

**Upload sizes:**

| Frames | Total bytes | Chunks | Time |
|--------|-------------|--------|------|
| 1 | 65,056 | 16 | ~1s |
| 10 | 648,256 | 159 | ~6s |
| 50 | 3,240,256 | 792 | ~28s |
| 141 (max) | 9,137,056 | 2,231 | ~78s |

**IMPORTANT:** Data chunks use Interface 2 output reports, NOT feature reports.
ACKs use `poll()` + `read()` on display interface fd with 300ms timeout.
**NEVER use `HIDIOCGFEATURE` on Interface 2** — crashes firmware, requires power cycle.

**CLI:**
- `ak820ctl image <file.png>` — resize, convert to RGB565, upload
- `ak820ctl gif <file.gif>` — extract frames, build header, upload animation

**WARNING:** Uploading a custom image replaces the firmware's built-in status
screen. There is no known USB command to restore the default display. Power-cycle
the keyboard (unplug and replug USB) to get the status screen back.

---

## Higher-Level Flows (Not Single Commands)

### `dump` / `restore` ⬜

Save and restore all keyboard settings.

```
dump:    read-id + read-lighting + read-perkey + read-stored-perkey → JSON
restore: parse JSON → set-lighting + upload-perkey + (optionally) set-time
```

### `watch` ⬜

Daemon that re-syncs the clock periodically (RTC drifts without correction).

```
loop: sleep N minutes → time sync
```

Could also monitor connect/disconnect events via 2.4G dongle protocol
(HID page `0xFF60`, status packet `0x05 0xA6`, connect=`0x01`/disconnect=`0x02`).

### `monitor` ⬜

Debug tool — sniff/log all HID traffic for reverse engineering.

---

## Not Possible (As Far As We Know)

| Feature | Reason |
|---------|--------|
| Key remapping | Different protocol (VIA variant PID `0x4021` under VID `0x3151`) |
| Macro recording | Not found in any RE effort for PID `0x8009` |
| Knob/encoder config | No rotary knob on AK820 Pro |
| Factory reset via USB | Not documented |
| DFU/bootloader entry via software | Requires physical pad short under spacebar |
| Display brightness (independent) | Controlled via lighting brightness, not a separate command |

## Hardware Notes

- MCU: HFD80CP100 (Sonix SN32F299)
- LCD controller: GC9107 (SPI)
- Flash: PY25Q128HA 16MB (SPI) — stores per-key colors, images, settings
- BT module: WCH CH582F (I2C)
- Bootloader VID/PID: `0x0C45`/`0x7140`
- Key matrix: 6 rows × 15 columns
