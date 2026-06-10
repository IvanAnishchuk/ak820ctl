# V1.13 Helper Functions — Disassembly & Semantics

Disassembly source: `disassemble_helpers.py` + literal-pool decoding.
Raw output: `ak820-re/ghidra-output/V1.13/helpers-capstone.txt` (out-of-tree).

This file resolves the central question left open by
[`unknown-commands.md`](unknown-commands.md): what do the "helper"
functions actually do, and does the `0x619e(N) → 0x6190(buf, off, count)`
pattern in the unknown-command handlers represent a real read or a stub?

## TL;DR

**The "stub" conclusion in V1.13 is wrong, AND the read/write classification in
[`unknown-commands.md`](unknown-commands.md) is also wrong.** Ghidra
pseudo-C (`ak820-re/ghidra-output/V1.13/{helpers,handlers}.md`, out-of-tree)
makes the real picture clear:

1. The two CMP chains in the original `firmware-analysis.md` notes (in the
   `ak820-re/` repo) are **two separate dispatchers** for two different
   events, not a single dispatch with a fall-through.
   - **First dispatch (`h_61c8_dispatcher` @ 0x061C8)** runs on a host SET_REPORT and
     does the immediate side-effect: flash write, state set, or trivial ack.
   - **Second dispatch** (separate function at `0x0645E`) runs as the USB GET_REPORT
     response producer and only knows how to queue chunked reads via `h_6190`.
2. Every "unknown" `0x6190` caller (`0x10`, `0x11`, `0x14`, `0x15`, `0x16`, `0x26`) uses
   the **exact same body shape** as the confirmed-working `0x22 READ_STORED_PERKEY`.
   They are real read commands; the probe-dump zeros/echoes are just default buffers.
3. `0x14` is **not a write** — its first-dispatch handler is a bare `return 1`. It's a
   48-chunk **read** from `DAT_00006764`. The 48-vs-49 chunk count is the only thing that
   distinguishes it from `0x15`.
4. `0x11` writes flash at `0x9400` from its first dispatch — it's not just a "read status
   and clear flag" command. It is a flash-erase-or-save trigger.

**Implication:** the entire "key remapping is non-functional in V1.13" thesis in
[`STATUS.md`](STATUS.md) is in doubt. The 48-chunk transfer is a *read*, not a write. The
actual write path (if any) is happening somewhere else, possibly via the SAVE (`0x02`)
session-finalize path or via the START (`0x18`) state machine. We need Phase 2 (cross-
firmware) and the Windows .exe analysis to find where keymap writes actually land.

## Function-by-function

### `0x619e` — chunk-budget check (calling convention guard)

Disassembly (28 bytes total):

```asm
0x0619e: mov    r1, r0              ; r1 = N (incoming arg)
0x061a0: ldr    r0, [pc, #0x120]    ; r0 = 0x20001374 (config base)
0x061a2: subs   r0, #0x14           ; r0 = 0x20001360
0x061a4: ldrb   r0, [r0, #0x1c]     ; r0 = byte[0x2000137C]   (counter low)
0x061a6: ldr    r3, [pc, #0x11c]    ; r3 = 0x20001374
0x061a8: subs   r3, #0x14
0x061aa: ldrb   r3, [r3, #0x1d]     ; r3 = byte[0x2000137D]   (counter high)
0x061ac: lsls   r3, r3, #8
0x061ae: orrs   r0, r3              ; r0 = uint16 LE at 0x2000137C
0x061b0: mov    r2, r0
0x061b2: cmp    r2, r1              ; counter ↔ N
0x061b4: ble    #0x61c4             ; counter ≤ N → success path
0x061b6: movs   r0, #0
0x061b8: ldr    r3, [pc, #0xf4]     ; r3 = 0x2000004c (busy flag)
0x061ba: strb   r0, [r3]            ; busy = 0
0x061bc: ldr    r3, [pc, #0x150]    ; r3 = 0x200000d9 (pending flag)
0x061be: strb   r0, [r3]            ; pending = 0
0x061c0: movs   r0, #1
0x061c2: bx     lr                  ; return 1 (= "rejected / done")

0x061c4: movs   r0, #0
0x061c6: b      #0x61c2              ; return 0 (= "ok, proceed")
```

**Meaning:** `0x619e(N)` reads a 16-bit "chunks-expected" counter from `0x2000137C` and asks
"is N still within budget?" If yes (counter ≤ N), returns 0 ("ok, the caller may schedule
a response"). If no, clears two protocol flags at `0x2000004C` and `0x200000D9` and returns
1 ("rejected").

This is **not** a per-request counter — `0x2000137C` is a stored config value (read once,
not incremented in this function). So `0x619e` is more like an ACL: "is this command
asking for ≤ the configured chunk budget?" If yes, allow it.

Pattern in callers: `bl 0x619e; cmp r0, #0; bne <skip>` — meaning: if `0x619e` rejected,
skip the `0x6190` call.

### `0x6190` — schedule a chunked response (read-side queue)

Disassembly (14 bytes total):

```asm
0x06190: ldr    r3, [pc, #0x12c]    ; r3 = 0x200000e0   (buffer-ptr slot)
0x06192: str    r0, [r3]            ; *0x200000e0 = r0  (source buffer address)
0x06194: ldr    r3, [pc, #0x150]    ; r3 = 0x200000e8   (offset slot)
0x06196: strh   r1, [r3]            ; halfword[0x200000e8] = r1  (start offset)
0x06198: ldr    r3, [pc, #0x150]    ; r3 = 0x200000d4   (count slot)
0x0619a: strb   r2, [r3]            ; byte[0x200000d4]   = r2   (chunk count)
0x0619c: bx     lr
```

**Meaning:** `0x6190(buf, offset, count)` writes three state variables that the USB
device-control routine later polls when generating GET_REPORT responses:

| RAM addr | Field | Width |
|----------|-------|-------|
| `0x200000E0` | source buffer pointer | 32 bits |
| `0x200000E8` | start offset within buffer | 16 bits |
| `0x200000D4` | chunk count (each 64 bytes) | 8 bits |

This is a **read-response setup**, not a write. The USB stack consumes these variables in
the GET_REPORT path. So any handler that calls `0x6190` is staging data to be **sent** to
the host on the next GET_REPORT.

This is the smoking gun: the unknown handlers calling `0x6190` are read handlers, end of
story.

### `0x18002` — flash range gate (guards every flash access)

```asm
0x18002: push   {r4, lr}
0x18004: mov    r4, r0              ; r4 = addr
0x18006: movs   r0, #1
0x18008: lsls   r0, r0, #0xf        ; r0 = 0x8000 (32 KB)
0x1800a: cmp    r4, r0
0x1800c: bhs    #0x18010            ; addr ≥ 0x8000 → do the I/O
0x1800e: pop    {r4, pc}            ; addr <  0x8000 → no-op return
```

**Meaning:** `0x18002(addr)` is the public entry to the flash I/O subsystem with a hard-coded
"addresses below 32 KB are off-limits" guard. The first 32 KB of flash hold firmware code
itself, so this stops a bogus command from overwriting code. The real flash code starts at
`0x18010`. The decompilation of that branch is left for the Ghidra pass — what matters here
is that the guard is permissive for everything ≥ 0x8000, which includes all the data regions
seen in the literal pool below.

### Flash data-region map (from literal pool at 0x06740-0x06790)

```
0x00008F80    config/header area
0x00009000    block A start
0x00009400    block A continuation
0x00009800    block B start
0x00009C00    per-key RGB (confirmed: CMD 0x23)
0x0000A000    block C
0x0000AC00    secondary block (confirmed: CMD 0x27)
```

Total span: 0x8F80–0xAC00 + region = roughly 7 KB of usable flash beyond per-key RGB.
The 0x14 handler (suspected keymap write) likely lands in one of the unconfirmed blocks
between 0x9000 and 0xAC00.

### `0x10d04` — reinit guard

```asm
0x10d04: push   {r4, lr}
0x10d06: ldr    r0, [pc, #0x144]
0x10d08: ldrb   r0, [r0]
0x10d0a: cmp    r0, #0
0x10d0c: beq    #0x10d10
0x10d0e: pop    {r4, pc}             ; flag non-zero → bail out
```

Flag check, early return if flag is set. The actual reinit logic is at `0x10D10`
(disassembly TBD in Ghidra pass). Used by session-cleanup paths.

### `0x5a4c` — set a peripheral bit and barrier

```asm
0x05a4c: cmp    r0, #0
0x05a4e: blt    #0x5a7c              ; mode < 0 → bail
0x05a50: lsls   r2, r0, #0x1b        ; r2 = (mode & 0x1F)
0x05a52: lsrs   r2, r2, #0x1b
0x05a54: movs   r1, #1
0x05a56: lsls   r1, r2               ; r1 = 1 << (mode & 0x1F)
0x05a58: ldr    r2, [pc, #0x3dc]     ; r2 = peripheral reg address
0x05a5a: str    r1, [r2]             ; *reg = bit
0x05a5c..0x05a78: nop chain + DSB + ISB
0x05a7c: bx     lr
```

This is **not** a generic LED-mode setter. The DSB/ISB pair around the store gives it away
as a memory-mapped peripheral write (probably the GPIO/PWM register for the keyboard's
backlight controller). The [`unknown-commands.md`](unknown-commands.md) interpretation
that this is "the LED-mode setter called with 0x13" is wrong — `0x13` (SET_LIGHTING)
does not call `0x5a4c` in the disassembly. We saw it called only from the factory-reset
path (`0x38`) and from the image upload path (`0x72`), with one specific bit-position
argument. It's more likely a **peripheral reset / clock-gate** call.

This is worth running through Ghidra to confirm — the call sites are what matter, not the
body.

### `0x61c8` — *this* IS the command dispatcher

```asm
0x061c8: push   {r4, r5, r6, lr}
0x061ca: mov    r4, r0              ; r4 = cmd
0x061cc: mov    r5, r1              ; r5 = packet ptr
0x061ce: mov    r0, r4
0x061d0: cmp    r4, #0x23
0x061d2: beq    #0x6286
0x061d4: bgt    #0x6218             ; cmd > 0x23 → upper half
0x061d6: cmp    r0, #0x15           ; (cmd ≤ 0x23) lower half
... binary tree dispatch ...
0x0623c: subs   r0, #0xf0           ; final case: cmd == 0xF0 (FINISH)
0x0623e: movs   r3, r0
0x06240: bl     #0x192f8             ; → session-finish helper
```

**Correction to existing docs:** the original (pre-Ghidra) `firmware-analysis.md` in
the `ak820-re/` repo describes the dispatcher as a "first dispatch (R0 comparisons,
offset 0x061D0-0x0623A)" followed by an unrelated "second dispatch (R5 comparisons,
offset 0x0645E-0x064B4)". They are **not** two parallel dispatch chains. The first
one is the body of `0x61c8(cmd, packet)`. The second one (0x0645E onward) is a
separate function — likely the IRQ/USB-EP1 callback that wakes the queued response
after `0x6190` has scheduled it. The R5 chain uses the **same** command code (since
the queued state still references the original cmd), but its job is to populate the
response buffer for transmission.

This means [`PROTOCOL.md`](PROTOCOL.md) and
[`unknown-commands.md`](unknown-commands.md) were double-counting handler addresses:
some "handlers" were dispatch entries, some were response-completion entries. The
Phase 2 dispatch extractor should label both kinds.

The `bl 0x192f8` at the tail is the session-finish routine (called for `0xF0`).

## Per-command corrected classification (from Ghidra)

Pseudo-C in `ak820-re/ghidra-output/V1.13/handlers.md` (out-of-tree).
The unifying schema:

- *first-dispatch* body = what runs on SET_REPORT with that command byte
- *second-dispatch* body = what runs on the GET_REPORT response producer

```
0x05  READ_ID       1st: trivial return       2nd: queues device info        — confirmed
0x10  read          1st: return 1             2nd: read 9 chunks @ DAT_6750  — was "stub", is real read
0x11  WRITE_FLASH+rd 1st: h_18002(0x9400)     2nd: read 9 chunks @ DAT_6750  — flash erase/save + read
0x12  READ_LIGHTING 1st: trivial              2nd: (elsewhere)               — confirmed
0x13  SET_LIGHTING  1st: h_18002(0x9800)      2nd: —                         — flash write at 0x9800 (was undocumented)
0x14  read          1st: trivial              2nd: read 48 chunks @ DAT_6764 — was "write 48 chunks", is read
0x15  read          1st: trivial              2nd: read 49 chunks @ DAT_6764 — was "stub", is real read
0x16  read          1st: trivial              2nd: read 1 chunk              — was "stub", is real read
0x19  set BT flag   1st: |= 0x40 on DAT_6730  2nd: —                         — confirmed
0x20  set state 0x32 1st: DAT_673C = 0x32    2nd: —                         — confirmed
0x22  READ_PERKEY   1st: trivial              2nd: read 9 chunks @ DAT_6760  — confirmed
0x23  WRITE_PERKEY  1st: h_18002(0x9C00)      2nd: —                         — confirmed
0x26  read          1st: trivial              2nd: read 9 chunks             — was "stub", is real read
0x27  WRITE_FLASH   1st: h_18002(0xAC00)      2nd: —                         — confirmed destructive
0x28  SET_TIME      1st: (uses START flow)    2nd: —                         — confirmed
0x38  factory reset 1st: trivial              2nd: multi-subsystem reinit    — confirmed destructive
0x72  UPLOAD_IMAGE  1st: trivial              2nd: (image path)              — confirmed
0xAB  unknown       1st: trivial              2nd: state = 4                 — unchanged
0xE0  NOP           1st: return 1             2nd: —                         — confirmed
```

**New finding not in any prior doc:** `0x13 SET_LIGHTING` writes flash at `0x9800` in its
first dispatch (`cmd_0x13_SET_LIGHTING` decompiles to `h_18002(0x9800)`). Was previously
attributed only to RAM state. This is the source of "SET_LIGHTING needs to be inside a
START/SAVE session" — the flash write is part of the SET, not the SAVE.

## Flash region map (corrected, from h_18002 callers)

| Addr  | Used by                                | Purpose                          |
|-------|----------------------------------------|----------------------------------|
| 0x9400 | `cmd_0x11_1st`                        | Unknown — possibly status/config block |
| 0x9800 | `cmd_0x13_SET_LIGHTING`               | Lighting mode persistence       |
| 0x9C00 | `cmd_0x23_WRITE_PERKEY`               | Per-key RGB                     |
| 0xAC00 | `cmd_0x27_destructive_1st`            | Secondary config / unknown      |

The `0x14`/`0x15`/`0x16`/`0x10`/`0x26` *read* buffers (`DAT_6750`, `DAT_6760`, `DAT_6764`,
etc.) are **RAM** addresses, not flash. They're staging buffers that the firmware copies
flash into on demand. So reading them on a factory-default device returns RAM zeros, not
flash contents.

## Open question for Phase 2/3

**Where does the actual keymap WRITE happen?** Nothing in the V1.13 first dispatch writes
flash for cmd `0x14` (the prime suspect for keymap-write). Possibilities:

1. It's hidden in the SAVE (`0x02`) handler — SAVE flushes a RAM buffer (the one cmd `0x20`
   primed by setting state `0x32`) to flash via `h_18002` at an address we haven't
   identified yet.
2. It's only present in a newer firmware. Phase 2's RS2 V1.28 dispatch dump will tell us.
3. The Windows driver doesn't actually remap keys via the proprietary protocol — it uses
   the VIA mode (PID 0x4021) after a mode switch. Phase 3 should find evidence either
   way in the .exe.
