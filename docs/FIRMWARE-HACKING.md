# AK820 Pro Firmware Hacking

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

The `fpb/ajazz-ak820-pro` repo contains stock firmware binaries:
- `AJAZZ_AK820PRO_PID_8009_V1.13_SN32F290.bin`
- Cross-compatible firmware from other keyboards using the same chipset

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
