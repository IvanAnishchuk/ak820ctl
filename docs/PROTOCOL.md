# AK820 Pro USB HID Protocol

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
| `0x13` | Lighting mode config | See lighting packet format below |
| `0x17` | Sleep timer setting | |
| `0x28` | **Time synchronization** | See time sync format below |
| `0x72` | Image/animation transfer init | LCD screen |
| `0x22` | Read custom per-key colors | From flash |
| `0x23` | Upload custom per-key RGB data | |
| `0xF5` | Read live per-key RGB state | |

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
- **Chunk size:** 4,096 bytes per output report
- **Chunks:** 9 total (8 full + 1 partial)
- **Header:** 256-byte GIF header prepended (frame count, timing)
- **Animation:** Up to 141+ frames supported
- **Acknowledgement:** Each chunk acknowledged by device (300ms timeout)
- **Initiation:** Send command `0x72` on Interface 3 first, then transfer data on Interface 2

## Per-Key Custom RGB (Command `0x23`)

- Mode `0x80` enables per-key custom colors
- 144 keys addressable
- Each key: position index + R, G, B (4 bytes per key)
- Total payload: 576 bytes, sent in multiple 64-byte packets

## Firmware Version Query (Command `0x01`)

Response contains version at bytes 2-4: `major.minor.patch`

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
