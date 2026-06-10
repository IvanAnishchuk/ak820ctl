# Ajazz AK820 Reverse Engineering Research

## Hardware Overview

| Property | Value |
|---|---|
| MCU | HFD80CP100 (rebrand of **Sonix SN32F299**, ARM Cortex-M based) |
| USB VID | `0x0C45` (Sonix Technology / registered as "Microdia") |
| USB PID (normal) | `0x8009` |
| USB PID (bootloader) | `0x7140` |
| HID Interfaces | 4 total |
| Command Interface | **Interface 3** - HID feature reports, 64 bytes |
| Display Interface | Interface 2 (Usage Page `0xFF68`) - interrupt OUT for LCD |
| Display | 0.85" 128x128 TFT LCD, GC9107 controller |
| Flash | PY25Q128HA, 16MB, SPI |
| Bluetooth Module | WCH CH582F |
| Key Matrix | 6 rows x 15 columns |
| Stock FW Version | V1.13 |

## Bootloader Access

Two pads under the spacebar (covered by 2 insulation layers + 1 removable foam strip).
Short these pads while plugging in USB -> MCU enters bootloader mode (VID/PID changes to `0x0C45`/`0x7140`).

This means **custom firmware is theoretically flashable** via the SonixQMK toolchain, though no AK820 QMK port exists yet (SN32F299 is not yet supported in SonixQMK - only F248/F248B/F268 are).

## Cross-Compatible Keyboards (Same Chipset Family)

These keyboards share VID `0x0C45` PID `0x8009` and likely the same protocol:
- Ajazz AK35i V3 MAX
- Ajazz AK980 PRO
- Helloganss XS75T
- JamesDonkey RS2
- Langtu LT84
- Leobod K81 Pro
- QK75N
- Womier S-K80

## Existing Linux Projects (Priority Order)

### 1. gohv/EPOMAKER-Ajazz-AK820-Pro (Rust - CLI + GUI)
- **URL:** https://github.com/gohv/EPOMAKER-Ajazz-AK820-Pro
- **Status:** Most complete, actively developed
- **Features:** Lighting (20 modes), sleep timer, clock sync, LCD image upload
- **Approach:** Wireshark USB captures, HID feature reports on Interface 3

### 2. TaxMachine/ajazz-keyboard-software-linux (C++)
- **URL:** https://github.com/TaxMachine/ajazz-keyboard-software-linux
- **Status:** Original/pioneering implementation, 39 stars
- **Features:** Lighting, sleep timer, clock
- **Includes:** Custom pcap parser in `analyze/` directory

### 3. fpb/ajazz-ak820-pro (Hardware Documentation)
- **URL:** https://github.com/fpb/ajazz-ak820-pro
- **Status:** 64 stars, pure documentation
- **Content:** PCB teardown, MCU identification, pinouts, bootloader access, stock firmware binaries

### 4. afonsusousa/mrworldwide-rs (Rust - Daemon + GTK4)
- **URL:** https://github.com/afonsusousa/mrworldwide-rs
- **Features:** RGB, settings, event trigger system (auto-switch OS layout on connect/disconnect)
- **Tested with:** 2.4G dongle

### 5. dantje/ajazz-ak35i-v3-max (C++ - Best Protocol Docs)
- **URL:** https://github.com/dantje/ajazz-ak35i-v3-max
- **Note:** Same VID/PID as AK820 Pro, has the most thorough `PROTOCOL.md`

### 6. Aiacos/ajazz-control-center (C++/Qt6 - Cross-platform)
- **URL:** https://github.com/Aiacos/ajazz-control-center
- **Status:** Early alpha, supports multiple Ajazz devices
- **AK820 Pro:** Listed as "scaffolded" (enumeration done, protocol mapping in progress)

### 7. SonixQMK Ecosystem
- **QMK fork:** https://github.com/SonixQMK/qmk_firmware
- **Flasher:** https://github.com/SonixQMK/sonix-flasher
- **Firmware dumper:** https://github.com/SonixQMK/sonix_dumper
- **Docs:** https://sonixqmk.github.io/SonixDocs/

### Other Related Projects
- `bernalirio/ak820pro-time-sync` - Rust, specifically for clock sync
- `afonsusousa/mrworldwide` - C, 2.4G dongle protocol RE
- `thanks4opensource/NotLinuxAjazzAK33RGB` - Python, AK33 (older model)
- `jkcdarunday/ajazzctl` - Python, AK66
- `aar-rafi/aks075-linux` - C, AKS075 screen image/GIF upload
- `xero/aks068-via` - VIA JSON for AKS068

## Official Software
- AK820 Pro driver: https://epomaker.com/blogs/software/ajazz-ak820-pro-driver
- Also: https://ajazzstore.com/blogs/software/ajazz-ak820-pro-driver
- **Note:** Official website has TLS/availability issues
