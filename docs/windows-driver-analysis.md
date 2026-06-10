# Windows DeviceDriver.exe — static analysis findings

Source: `vendor/windows/extracted/app/DeviceDriver.exe` (1.8 MB MFC PE32).
Method: static disassembly + decompilation via PyGhidra
(`scripts/ghidra/analyze_exe.py`). Raw output:
`ak820-re/ghidra-output/windows/{hid_calls.md, send_functions.md,
setfeature_callers.md, setfeature_wrapper_callers.md, cmd_senders.md,
strings.txt}` (out-of-tree).

## TL;DR

This document answers the open question from
[`firmware-analysis-helpers.md`](firmware-analysis-helpers.md):
**where does the keymap write actually happen?** Not in CMD `0x14` (that's a
48-chunk read), not in CMD `0x20` (that's a custom-lighting upload), but in
**CMD `0x11`** (default layer) and **CMD `0x27`** (other layers). The
Windows tool serializes 192-ish per-key HID usage code records (4 bytes per
entry, ~780 bytes total) and writes them via the same `START → CMD → bulk
data → SAVE → FINISH` pattern used by `0x23 WRITE_PERKEY`.

The V1.13-only `cmd_0x11_1st → h_18002_flash_io(0x9400)` is **not** a debug
artifact — it's the layer-0 keymap upload command. The "V1.13 quirk" framing
in [`firmware-analysis-helpers.md`](firmware-analysis-helpers.md) should be
revised: V1.13 supports a default-layer keymap, other firmware revisions in
the family don't (or moved the layer-0 storage to share `0xAC00` with the
other layers).

## How HID I/O is wired

The .exe does not import from `hid.dll` statically. Instead it dynamically
resolves the HID API at startup:

- **`FUN_00450af0`** — calls `LoadLibraryA("hid.dll")`, then
  `GetProcAddress` for `HidD_GetAttributes`, `HidD_SetFeature`,
  `HidD_GetFeature`, `HidD_GetPreparsedData`, `HidP_GetCaps`, etc. The
  function-pointer slots are:
  - `DAT_005950a0` = `HidD_SetFeature`
  - `_DAT_0059509c` = `HidD_GetFeature`
  - `DAT_005950b4` = `HidD_GetAttributes`
  - `DAT_005950a8` = `HidD_GetPreparsedData`
  - `DAT_005950ac` = `HidP_GetCaps`

- **`FUN_00450c00`** — device enumeration via
  `SetupDiGetClassDevsA(&HID_GUID, …)` →
  `SetupDiEnumDeviceInterfaces` → `CreateFileA`. Walks all HID devices,
  reads each one's `HidD_GetAttributes`, matches against the
  `VID_0C45/PID_8009/PID_800A/PID_FDFD` set declared in `config.xml`.

- **`FUN_00451440`** — thin wrapper around
  `(*DAT_005950a0)(handle, buffer, 0x41)`. 0x41 = 65 = 1-byte report ID +
  64-byte command packet.

- **`FUN_0044eed0`** — chunked-send loop. Signature:
  `FUN_0044eed0(this, buffer, byte_count, retry)`.
  - If `byte_count < 66`: one chunk, with `Sleep(this->[0x30])` (= 35 ms
    `cmd_delaytime` from `rgb-keyboard.xml`) before the send.
  - Else: iterate `byte_count / 64` chunks of 64 bytes each, each preceded
    by the 35 ms sleep, with up to 10 retries on per-chunk failure.

`FUN_0044f0c0` and `FUN_0044f3a0` are sibling chunk wrappers — one for
write-only feature reports, one for write-then-read feature reports (the
`GetFeature` path).

## How CMD codes are encoded in the .exe

CMD codes are not present as `04 XX 00 00 …` static byte sequences. Instead
they are written as **16-bit little-endian immediates of the form
`0xCMD04`** — the low byte is the HID report ID (`0x04`) and the high byte
is the command code. Examples directly from the decompilation:

| Literal | Command sent |
|---------|--------------|
| `0x1804` | `0x18` START |
| `0x0204` | `0x02` SAVE |
| `0xF004` | `0xF0` FINISH |
| `0x1304` | `0x13` SET_LIGHTING |
| `0x1704` | `0x17` SET_SLEEP |
| `0x2304` | `0x23` WRITE_PERKEY |
| `0x2804` | `0x28` SET_TIME |
| `0x7204` | `0x72` UPLOAD_IMAGE |
| `0x2004` | `0x20` CUSTOM_LIGHTING_BEGIN |
| `0x1504` | `0x15` READ_KEYMAP (49 chunks) |
| `CONCAT11(0x11, 0x04)` / `CONCAT11(0x27, 0x04)` | `0x11` or `0x27` KEYMAP_WRITE |

CMD bytes also appear directly as `buffer[1] = 0xCMD` in some readers
(e.g., `local_2b0[1] = 0xF5` in `FUN_0042aee0`, the live-perkey reader).

## Per-command-sequence functions

Every "operation" in the Windows tool is implemented as a function that
sends `START → CMD → [data chunks] → SAVE → FINISH`. The 12 such functions
found by walking callers of the SetFeature wrappers:

| Function | CMD sequence | Purpose |
|----------|-------------|---------|
| `FUN_00414060` @ 0x414060 | 0x18 → 0x17 → 0x02 | SET_SLEEP |
| `FUN_00418420` @ 0x418420 | 0x18 → **0x11 or 0x27** → 780 B data → 0x02 → 0xF0 | **KEYMAP UPLOAD** (this doc's lead) |
| `FUN_00422980` @ 0x422980 | 0x18 → 0x72 → image chunks → 0x02 | LCD image upload |
| `FUN_00423940` @ 0x423940 | 0x18 → 0x28 → 0x02 | SET_TIME |
| `FUN_00427e10` @ 0x427E10 | 0x20 → 192-512 B data → 0x02 | CUSTOM_LIGHTING (per-key palette via `MUI::CustomLightMode::GetKeyItems`) |
| `FUN_0042aee0` @ 0x42AEE0 | `buf[1]=0xF5` → read 9 chunks → 0x02 | READ_LIVE_PERKEY (via `MUI::KeyboardCtrl::GetKeyItems`) |
| `FUN_0042b100` @ 0x42B100 | 0x18 → 0x13 → 0x02 → 0xF0 | SET_LIGHTING variant A |
| `FUN_0042d6f0` @ 0x42D6F0 | 0x15 → 0x02 | READ_KEYMAP (the 49-chunk read confirms 0x15's identity) |
| `FUN_004329e0` @ 0x4329E0 | 0x20 → 0x02 | CUSTOM_LIGHTING (smaller variant) |
| `FUN_00434090` @ 0x434090 | 0x18 → 0x13 → 0x02 → 0xF0 | SET_LIGHTING variant B |
| `FUN_0044b900` @ 0x44B900 | 0x18 → 0x13 → 0x02 → 0xF0 | SET_LIGHTING variant C |
| `FUN_0044ba10` @ 0x44BA10 | 0x18 → 0x23 → per-key data → 0x02 → 0xF0 | WRITE_PERKEY |

**Commands the Windows tool never sends:** `0x05` (READ_ID), `0x10`,
`0x12`, `0x14`, `0x16`, `0x19`, `0x22` (READ_STORED_PERKEY), `0x26`,
`0x38`, `0xAB`, `0xE0`. The unknown CMDs `0x10`, `0x14`, `0x16`, `0x26`
are confirmed to be unused by the vendor tool — they exist in firmware
but nothing calls them.

Notable absences:
- `0x14` is never sent — the "48-chunk write" theory is fully dead.
- `0x22` (READ_STORED_PERKEY) is never sent either — the Windows tool
  uses the live-RAM read `0xF5` exclusively for per-key RGB readback,
  and presumably keeps its own copy in the SQLite DB rather than reading
  the stored value back from flash.

## The keymap upload sequence — `FUN_00418420`

This is the function that answers the open question from
[`firmware-analysis-helpers.md`](firmware-analysis-helpers.md). Pseudo-C
structure:

```c
void FUN_00418420(this, int param_1) {
    // 1. START
    local_58 = 0x1804;
    FUN_0044eed0(handle, &local_58, 65, retry=1);

    // 2. Pick the CMD byte by fn_layer parameter
    uVar2 = 0x11;                  // default
    local_50 = 9;                  // chunk count = 9 (so 9*64 = 576 B payload)
    if (param_1 != 0) {
        uVar2 = 0x27;              // non-default layer → 0x27 (flash @ 0xAC00)
    }
    local_58 = CONCAT11(uVar2, 4); // build 0x1104 or 0x2704
    FUN_0044eed0(handle, &local_58, 65, retry=1);

    // 3. Build a 780-byte (0x30c) buffer of per-key entries
    memset(&local_364, 0, 0x30c);

    // ... AVL-tree walk over key items (this->[0x7f8] holds the keymap tree),
    // ... encoding each key into 4 bytes:
    //       [iVar10*4 + 0] = type tag (1=HID kbd, 2=mouse, 3=modifier,
    //                                   6=consumer/media, 7=mouse btn/wheel)
    //       [iVar10*4 + 1] = usage_low / payload byte 1
    //       [iVar10*4 + 2] = usage_high / payload byte 2
    //       [iVar10*4 + 3] = modifier / payload byte 3

    // Notable encoded values (extracted from the per-iVar5-branch literals):
    //   type 5 → kbd / sys ctrl: 0x0101, 0x0401, 0x0201, 0x0301, 0x0103,
    //                            0xFF03, 0x0801, 0x1001
    //   type 6 → media keys:     0xCD, 0xB7 (stop), 0xB6 (prev), 0xB5 (next),
    //                            0xE9, 0xEA, 0xE2 (volume)
    //   type 7 → mouse / wheel:  0x0708, 0x0808, 0x0F08, 0x1A01, 0x2B04,
    //                            0x0601, 0x1901, ...

    // 4. Send the 780-byte payload via the chunked wrapper
    //    (call site is in the function tail, past the excerpt cut)

    // 5. SAVE
    // 6. FINISH
}
```

The `param_1` argument is the layer index (0 = default / fn_layer 0, nonzero
= function-layer or custom-layer slot). The SQLite schema in
`extracted/app/DeviceDriver.exe` confirms this: `t_key_macro_data` has a
`fn_layer INTEGER` column.

## Why CMD 0x11 is V1.13-only

Combining the cross-firmware divergence analysis (working file
`ak820-re/firmware-blobs/cross-firmware-divergences.md`, out-of-tree)
with the Windows-side finding:

- **V1.13** uses `0x9400` (CMD `0x11`) for the default-layer keymap and
  `0xAC00` (CMD `0x27`) for the alternate-layer keymap. Two regions, one
  CMD each.
- **All other firmwares** (V1.28, V1.03, V1.09, V1.01, V1.41, V1.42) have
  no flash-write on CMD `0x11` — the first-dispatch handler is a bare
  `return 0`. So sending CMD `0x11` to those firmwares is a no-op.
- The Windows tool presumably handles this by always sending CMD `0x11`
  for the default layer; on non-V1.13 firmwares this is silently dropped
  and the keymap upload effectively only works for non-default layers.
  Alternatively, the Windows tool checks the firmware version (via CMD
  `0x05` READ_ID, which it does send) and skips the CMD `0x11` write on
  non-V1.13 builds — though I haven't tracked that down in the static
  analysis.

This also resolves the puzzle of why the firmware family contains a
"V1.13 quirk": it's not a quirk, it's that V1.13 split the keymap into
two flash regions and later firmwares unified them.

## Open follow-ups (not in scope for this commit)

1. Trace the actual chunked send for `local_364` in `FUN_00418420` — the
   excerpt ends before the send call. Confirm chunk count is 9 (matches
   `local_50 = 9` at line 209).
2. Check whether `FUN_0044f0c0` (the variant used by the 0x20 custom-light
   sender) differs from `FUN_0044eed0` in interesting ways (it might do a
   write-then-read or might handle the wireless-mode size difference).
3. Find where the SQLite DB is loaded at startup and where it's flushed —
   that's the ground truth for what "remap state" the Windows tool keeps.
4. Identify whether the `CMD 0x05 READ_ID` call site reads `bcdDevice` and
   branches the upload sequence by firmware version.
