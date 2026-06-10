# Unknown Command Analysis — Firmware Handler Disassembly

Analysis of all unknown command handlers from the AK820 Pro firmware V1.13.

> **Status note (2026-06-10):** the original "stub" / "destructive write" verdicts in this
> file were based on Capstone disassembly alone and turned out to be partially incorrect.
> See [`firmware-analysis-helpers.md`](firmware-analysis-helpers.md) and the
> Ghidra decompile in the `ak820-re/` repo
> (`ghidra-output/V1.13/handlers.md`) for the Ghidra-decompiled view.
> **Each section below has a "REVISED" line at the bottom.**
> When the original analysis and the Ghidra view conflict, trust the Ghidra view.

## Key helper functions

- `0x619e(chunk_count)` — Prepare to receive/send N data chunks (64 bytes each)
- `0x6190(buffer, offset, count)` — Send data response back to host
- `0x18002(flash_addr)` — Flash memory operation (read/write at shifted address)
- `0x10d04()` — Reset/reinitialize something (used by session cleanup)
- `0x5a4c(mode)` — Set LED mode (called with 0x13 = SET_LIGHT)
- `0x61c8(cmd, data)` — Process received command packet

## Command Analysis

### CMD 0x10 — READ KEYBOARD CONFIG

**First dispatch:** `movs r0, #1; b 0x6250` — returns 1 (success marker)

**Second dispatch (0x064D0):** Calls `0x619e(9)` then `0x6190(buffer, r4+1, 1)`.
This is the exact same pattern as READ_LIGHTING (0x12) — reads a config block
from a different buffer address.

**Verdict:** Reads 9 chunks of keyboard configuration (576 bytes). Likely returns
key matrix or general keyboard settings. **Safe to probe.**

**REVISED:** Confirmed read of 9 chunks from RAM buffer at `DAT_00006750` (resolved
RAM, not flash). First-dispatch handler is a trivial `return 1`. Same calling
convention as `0x22 READ_STORED_PERKEY`. The factory-default zeros we saw in the
probe are just the staging buffer at boot.

---

### CMD 0x11 — READ STATUS/FLAGS

**Handler (0x064E8):** Clears bit 1 of a flag byte (`bics r0, #2`), then
calls `0x619e(9)` and `0x6190(buffer, r4, 2)`.

The flag clearing + data read pattern suggests this reads a status register
and simultaneously clears a "data ready" flag.

**Verdict:** Read-and-clear status/notification register. Returns 2 chunks.
**Safe to probe.**

**REVISED:** Wrong on both axes. (a) The first-dispatch handler actually triggers a
**flash write** at `0x9400` via `h_18002_flash_io(&DAT_00009400)`. (b) The second
dispatch reads 9 chunks (not 2) from `DAT_00006750` — the same buffer as `0x10`.
So `0x11` is *flash-save-and-readback*. The "clears bit 1" code is in the
second-dispatch read path, clearing a "data ready" interrupt flag after the read is
queued. **Not safe to probe blindly** — it modifies flash at `0x9400`. What lives at
`0x9400` is still unidentified (Phase 2 may reveal via cross-firmware comparison).

**REVISED (Phase 3, 2026-06-10):** Identified via Windows-driver analysis.
`0x11` is the **default-layer keymap upload command** in V1.13. Sequence:
`START → 0x11 → 9 chunks × 64 bytes of per-key HID usage codes → SAVE →
FINISH`. The flash write at `0x9400` is the default-layer (`fn_layer == 0`)
keymap storage. Non-default layers use `0x27` (flash at `0xAC00`).
Confirmed by `vendor/windows/extracted/app/DeviceDriver.exe`'s
`FUN_00418420` which picks the CMD byte by layer index. So this is **not**
a "V1.13 quirk" — V1.13 supports a *two-region* keymap (default + alternate),
and later firmwares (V1.28+) folded both layers into a single region at
`0xAC00`. See [`windows-driver-analysis.md`](windows-driver-analysis.md) for
full sequence.

---

### CMD 0x14 — WRITE LARGE CONFIG BLOCK

**Second dispatch (0x065DC):** Calls `0x619e(0x30)` — that's **48 decimal chunks**
(48 × 64 = 3,072 bytes!). Then calls `0x6190(buffer, r4+1, 1)`.

This is the largest data transfer of any command. 3KB is enough for:
- Full keymap: 6 rows × 15 cols × 2 bytes × 4 layers = 720 bytes/layer × 4 = 2,880 bytes
- Or macro storage

**Verdict:** **WRITE KEYMAP or WRITE MACRO DATA.** Receives 48 chunks of data.
This is very likely the key remapping write command. **Needs USB capture to confirm
packet format before probing.**

**REVISED — WRONG DIRECTION.** Ghidra pseudo-C makes it clear: `0x14` is a **read**,
not a write. First-dispatch is bare `return 1`. Second-dispatch calls
`h_6190(DAT_00006764, ..., 1)` after `h_619e(0x30)` — i.e. it schedules a 48-chunk
response. The 48-chunk number was real but the direction was inferred from a wrong
match against the `0x22`/`0x23` write/read pair. The actual keymap-write path is
**still unidentified** — possibly hidden in the SAVE (`0x02`) handler, possibly
absent from V1.13 entirely, possibly Windows-side via the VIA mode switch. See
[`firmware-analysis-helpers.md`](firmware-analysis-helpers.md) "Open question for
Phase 2/3".

**REVISED (Phase 3, 2026-06-10):** Windows-driver analysis confirms `0x14` is
**never sent** by the vendor tool. Whatever buffer `DAT_00006764` points to is
populated by something else (possibly a debug command, possibly leftover
firmware-internal state). The keymap upload path goes through `0x11`/`0x27`,
not `0x14`. See [`windows-driver-analysis.md`](windows-driver-analysis.md).

---

### CMD 0x15 — READ KEYMAP/MACRO

**Second dispatch (0x065F4):** Clears bit 1 of flag, calls `0x619e(0x31)` — that's
**49 decimal chunks** (49 × 64 = 3,136 bytes). Then calls `0x6190(buffer, r4, 2)`.

This is paired with CMD 0x14 (48 write chunks → 49 read chunks including header).
The asymmetry (49 vs 48) suggests a 1-chunk header + 48 data chunks.

**Verdict:** **READ KEYMAP or READ MACRO DATA.** This is the read counterpart
to 0x14. **Safe to probe — it's a read command.**

**REVISED:** Confirmed read. 49 chunks from `DAT_00006764` (same RAM buffer as
`0x14`). The 48-vs-49 distinction is the only difference — possibly a header byte.
Both target the same RAM region, so `0x14` and `0x15` are reading the same data with
slightly different framing. Whatever the Windows tool stages here would have to be
written by some other command, since the V1.13 first-dispatch for both is empty.

---

### CMD 0x16 — READ SMALL CONFIG

**Second dispatch (0x06616):** Calls `0x619e(1)` then `0x6190(buffer, r4+1, 1)`.

Single chunk read (64 bytes). Very similar to READ_ID (0x05).

**Verdict:** Read a small configuration block (64 bytes). Could be layer state,
sleep config, or BT config. **Safe to probe.**

**REVISED:** Confirmed 1-chunk read. The `FF`s we saw in the probe dump are because
the source buffer references unprogrammed flash data that gets staged into RAM at
boot — on a default device that region is `FF`.

---

### CMD 0x19 — SET FLAG (BT/WIRELESS?)

**First dispatch (0x06356):** Loads a flag byte, ORs with `0x40` (bit 6), stores
it back. Then returns 1.

This is a simple flag-set operation. Bit 6 of the flag byte is toggled ON.
Compare with the paired code that clears bit 6 (`bics r0, #0x40`).

**Verdict:** **Enable wireless/BT mode flag.** The `0x40` bitmask suggests a
mode switch (e.g., BT pairing mode, 2.4G mode). **Probably safe but may change
connection behavior.**

**REVISED:** Confirmed. First-dispatch ORs bit 6 of `DAT_00006730`. No second-dispatch
handler — pure state-set.

---

### CMD 0x20 — SET STATE / WRITE CONFIG MARKER

**First dispatch (0x06396):**
```asm
movs r0, #0x32      ; value = 50 decimal (or 0x32)
ldr  r1, [pc, ...]  ; load address of state variable
strb r0, [r1]       ; store 0x32 to state variable
movs r0, #1         ; return 1
b    0x6250
```

**Second dispatch (0x06650):**
```asm
ldr  r0, [flag_addr]
bics r0, #2         ; clear bit 1 of flag
strb r0, [flag_addr]
movs r0, #2         ; set a different state to 2
strb r0, [state2]
strh r4, [buf_addr] ; store half-word from r4 (packet data)
movs r0, #1         ; set yet another flag to 1
strb r0, [flag3]
b    exit
```

This sets state variable to `0x32` (50) and stores packet data (r4) as a
half-word. The value 0x32 matches the constant used in the flash subsystem
as a "flash block type 2" marker — **this strongly suggests keymap flash data**.

**Verdict:** **INITIATE KEYMAP WRITE.** Sets firmware into "receive keymap data"
mode by writing the 0x32 state marker. The actual keymap data would follow
via CMD 0x14 (which handles 48 chunks). **This is the keymap setup command.**

**REVISED — partial.** Confirmed: first-dispatch sets `DAT_0000673C = 0x32`. But the
"data would follow via CMD 0x14" theory does **not** work — `0x14` is a read, not a
write (see revised CMD 0x14 above). The `0x32` state marker must be consumed by a
*different* command path we haven't traced yet. Candidates: the SAVE (`0x02`)
handler routes by this state, or an unmapped command byte we missed. Phase 2's
extractor should look for any code that reads `DAT_0000673C` and compares it to
`0x32`.

**REVISED (Phase 3, 2026-06-10):** Phase 3 confirmed `0x20` is the
**custom-lighting upload preamble**, not keymap-related. Sequence in
`DeviceDriver.exe::FUN_00427e10`: `0x20 → 192-512 bytes of per-key RGB palette
data (via `MUI::CustomLightMode::GetKeyItems`) → SAVE`. The 0x32 state byte
routes the upcoming chunked data to the custom-lighting RAM staging area.
Distinct from `0x23 WRITE_PERKEY` — both upload per-key colors, but `0x23`
writes 9 chunks × 64 bytes (the persistent palette stored at flash `0x9C00`),
while `0x20` writes a smaller variable-size buffer to a different RAM
location (likely a "current frame" buffer for animated custom modes).

---

### CMD 0x26 — READ FLASH DATA BLOCK

**Second dispatch (0x0650A):** Calls `0x619e(9)` then `0x6190(buffer, r4+1, 1)`.

Same pattern as CMD 0x10 and READ_STORED_PERKEY (0x22). Reads 9 chunks
from a different flash address.

**Verdict:** Read a 9-chunk data block from flash. Different buffer than 0x10
or 0x22. Could be custom macro data or a secondary config region. **Safe to probe.**

**REVISED:** Confirmed real read. First-dispatch trivial. Second-dispatch queues a
9-chunk response. The pairing of `0x26 read` with `0x27 write@0xAC00` (below) holds
up — they're a read/write pair for the secondary block.

---

### CMD 0x27 — WRITE FLASH DATA BLOCK

**First dispatch (0x06266):**
```asm
movs r0, #0x2b      ; 0x2b << 10 = 0xAC00
lsls r0, r0, #0xa
bl   0x18002        ; flash operation at address 0xAC00
movs r0, #1
b    0x6250
```

Calls the flash write function with address `0x2B << 10 = 0xAC00`.
Compare with CMD 0x23 (PERKEY) which uses `0x27 << 10 = 0x9C00`.

**Verdict:** **Write data to flash at offset 0xAC00.** This is a secondary
flash region (per-key is at 0x9C00, this is at 0xAC00 = 4KB later).
Likely macro data or secondary keymap. **DESTRUCTIVE — writes flash.**

---

### CMD 0x38 — FACTORY RESET

**Second dispatch (0x06686):**
```asm
; Clear flags
bics r0, #2
; Clear state
str  #0, [state]
strh r4, [buf]
movs r0, #5          ; set state to 5
strb r0, [state2]
; Chain calls to MULTIPLE subsystem initializers:
bl   0x5a4c(0x13)   ; re-init LED mode
bl   0x17df4         ; reinit subsystem 1
bl   0x17e12         ; reinit subsystem 2
bl   0x7ac4          ; reinit subsystem 3
bl   0x583e          ; reinit subsystem 4
bl   0x598e          ; reinit subsystem 5
; Set final state
movs r0, #0xe        ; state = 14
strb r0, [state3]
```

This calls 6 different initialization functions — the same chain called by
the IMAGE upload handler. It resets LED mode, reinitializes multiple subsystems.

**Verdict:** **FACTORY RESET or FULL REINIT.** Resets keyboard to default
state by reinitializing all subsystems. **DESTRUCTIVE — resets all settings.**

---

### CMD 0xAB — SET MODE/STATE 4

**Second dispatch (0x067AC):**
```asm
bics r0, #2          ; clear bit 1 of flag
strb r0, [flag_addr]
movs r0, #4          ; set state to 4
strb r0, [state]
b    exit
```

Sets a state variable to 4. This is a simple state transition — could put
the firmware into a special mode.

**Verdict:** **ENTER SPECIAL MODE (firmware update? diagnostic?).**
Sets state to 4 which is different from normal operation. The COMMANDS.md
note said "possibly firmware update related." **Could be DFU mode trigger.**

---

### CMD 0xE0 — NOP (returns 1)

**First dispatch (0x06314):** Branches to 0x6342 which is just:
```asm
movs r0, #1
b    0x6250     ; return success
```

**Verdict:** **No-op / ping / keepalive.** Returns success without doing anything.
**Safe to call.**

---

## Summary: Key Remapping Path

Based on the analysis, key remapping likely works like this:

1. **CMD 0x15** — Read current keymap (49 × 64-byte chunks = 3,136 bytes)
2. **CMD 0x20** — Initiate keymap write (sets state marker 0x32)
3. **CMD 0x14** — Upload new keymap data (48 × 64-byte chunks = 3,072 bytes)
4. **CMD 0x02** — SAVE to persist to flash

The flash layout appears to be:
- `0x9C00` — Per-key RGB data (CMD 0x23/0x22, 9 chunks)
- `0xAC00` — Secondary config/macro data (CMD 0x27, 9 chunks)
- Keymap data — stored in the 48-chunk block (address TBD)

## Safety classification

| CMD | Risk | Action |
|-----|------|--------|
| 0x10 | Safe | Read-only config query |
| 0x11 | Safe | Read-only status query |
| 0x14 | **Destructive** | Writes 3KB data (keymap?) |
| 0x15 | Safe | Read-only (49 chunks) |
| 0x16 | Safe | Read-only (1 chunk) |
| 0x19 | Moderate | Sets wireless flag |
| 0x20 | Moderate | Sets state for keymap write |
| 0x26 | Safe | Read-only (9 chunks) |
| 0x27 | **Destructive** | Writes flash at 0xAC00 |
| 0x38 | **Destructive** | Factory reset |
| 0xAB | **Unknown** | Enters special mode |
| 0xE0 | Safe | No-op / ping |

## REVISED safety classification (2026-06-10, from Ghidra)

| CMD | Risk | Action (corrected) |
|-----|------|--------------------|
| 0x10 | Safe | 9-chunk read from RAM buffer DAT_6750 |
| 0x11 | **Destructive** | First-dispatch writes flash at `0x9400`; second-dispatch reads back 9 chunks. Was wrongly labeled "safe". |
| 0x14 | Safe | 48-chunk read from RAM buffer DAT_6764 (not a write) |
| 0x15 | Safe | 49-chunk read from same RAM buffer DAT_6764 |
| 0x16 | Safe | 1-chunk read |
| 0x19 | Moderate | OR bit 6 of state byte |
| 0x20 | Moderate | Sets state-byte = 0x32. The downstream consumer of that state is *unidentified* (was wrongly assumed to be 0x14). |
| 0x26 | Safe | 9-chunk read from secondary buffer |
| 0x27 | Destructive | Flash write at 0xAC00 — unchanged |
| 0x38 | Destructive | Factory reset — unchanged |
| 0xAB | Unknown | Sets state to 4 — unchanged |
| 0xE0 | Safe | NOP / ping — unchanged |

Additional Ghidra-only finding (not in this file before): `0x13 SET_LIGHTING` also
calls `h_18002(0x9800)` in its first dispatch. So SET_LIGHTING is *itself* a flash
write, not just a RAM update — explaining why it needs the START/SAVE wrapping.

## Next steps

1. **Probe safe read commands** (0x10, 0x11, 0x15, 0x16, 0x26, 0xE0) to capture response data
2. **Capture Windows driver traffic** while remapping keys to confirm the 0x15→0x20→0x14 sequence
3. **Decode the 3KB keymap format** from the 0x15 response (6×15 matrix × 4 layers × 2 bytes?)
