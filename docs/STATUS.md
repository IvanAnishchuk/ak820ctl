# AK820 Reverse Engineering — Status & Next Steps

**Last updated:** 2026-06-10 (end of Phase 3/4)

> Vendored from the `ak820-experiments/ak820-re/` reverse-engineering
> repo (sibling of this CLI). Out-of-tree references are kept as
> sibling-repo paths; in-tree references are rewritten to local
> `docs/` siblings.

## Headline result

The keymap path is now fully understood.

The Windows control utility (`vendor/windows/extracted/app/DeviceDriver.exe`)
uploads keymaps via:

```
START (0x18)
    → CMD 0x11   (default layer)        OR
       CMD 0x27  (alternate layers)
    → 9 chunks × 64 bytes of 4-byte-per-key HID usage codes
       (type tag, usage low, usage high, modifier)
    → SAVE (0x02)
    → FINISH (0xF0)
```

`0x11` writes flash at `0x9400`, `0x27` writes flash at `0xAC00`. V1.13 is
the only firmware in the family with a working `0x11` handler — newer
firmwares (V1.28 +) folded both layers into `0xAC00`. So V1.13 is the only
firmware that supports a *separate* default-layer keymap; on other
firmwares the default-layer write is a silent no-op and only the alternate
layer takes effect.

This kills the prior session's reading of CMD `0x14` as "the keymap write"
— `0x14` is a 48-chunk read, never sent by the vendor tool. See
[`windows-driver-analysis.md`](windows-driver-analysis.md) for the full
evidence trail (decompiled `FUN_00418420` etc.).

## Phase status

| # | Phase | Status |
|---|-------|--------|
| 1A | Capstone helper disasm (`disassemble_helpers.py`) | ✅ |
| 1B | Ghidra helper decompile (`scripts/ghidra/analyze_firmware.py`, `ghidra-output/V1.13/`) | ✅ |
| 1C | Resolve stub-vs-default-buffer ([`unknown-commands.md`](unknown-commands.md), [`firmware-analysis-helpers.md`](firmware-analysis-helpers.md)) | ✅ |
| 2A | Pattern-based dispatch extractor (`extract_dispatch.py`) | ✅ |
| 2B | Extract dispatch tables for all 8 blobs (`firmware-blobs/`) | ✅ |
| 2C | Ghidra batch decompile of all blobs (`ghidra-output/{RS2_V1.28,...}/`) | ✅ |
| 3A | Acquire + triage Windows .exe (`vendor/windows/`) | ✅ |
| 3B | Extract HID literals + cross-refs from .exe (`ghidra-output/windows/`) | ✅ |
| 3C | Identify CMD codes the Windows tool sends ([`windows-driver-analysis.md`](windows-driver-analysis.md)) | ✅ |
| 4A | LCD chunk size = 4123 ([`PROTOCOL.md`](PROTOCOL.md)) | ✅ |
| 4B | Citations + lsusb capture (`dumps/lsusb.txt`) | ✅ |
| 4C | VIA dual-mode variant ([`PROTOCOL.md`](PROTOCOL.md)) | ✅ |
| 4D | Update STATUS.md | ✅ (this file) |
| 14 | Final verification — re-probe live device | ⏸ pending |
| 16 | Update upper-directory umbrella docs | ⏸ pending |

## Key revisions vs. prior session's STATUS.md

| Old claim | New claim |
|-----------|-----------|
| "cmd 0x14 is the keymap write" | Wrong — 0x14 is a 48-chunk read, never sent by the vendor tool. |
| "cmd 0x11's flash write at 0x9400 is a V1.13 debug artifact" | Wrong — it's the **default-layer keymap write**, intentional. |
| "no firmware has the keymap-write path" | Wrong — V1.13 has both layers (0x11 + 0x27), other firmwares have only 0x27. |
| "the Windows tool probably uses VIA mode for remap" | Wrong — it uses the proprietary `0x11`/`0x27` path. VIA support is unrelated. |
| "LCD chunks are 4096 bytes" | LCD chunks are **4123 bytes** on the wire (4096 + 27-byte trailer). Confirmed empirically + via 2 reference impls. |

## What the Windows tool sends

12 distinct CMD codes:
`0x02 SAVE`, `0x05 READ_ID`, **`0x11 KEYMAP_DEFAULT`**, `0x13 SET_LIGHTING`,
`0x15 READ_KEYMAP`, `0x17 SET_SLEEP`, `0x18 START`, `0x20 CUSTOM_LIGHTING`,
`0x23 WRITE_PERKEY`, **`0x27 KEYMAP_ALT`**, `0x28 SET_TIME`, `0x72 UPLOAD_IMAGE`,
`0xF0 FINISH`, `0xF5 READ_LIVE_PERKEY`.

CMDs that exist in firmware but the vendor tool never sends:
`0x10`, `0x12` (`READ_LIGHTING` — only the lighting *set* is used),
`0x14`, `0x16`, `0x19` (V1.13-only), `0x22` (READ_STORED_PERKEY),
`0x26`, `0x38` (factory reset), `0xAB`, `0xE0`.

These are likely vestigial / debug / firmware-internal-test commands.

## What's still open

- **Live verification:** run `uv run python probe_commands.py` against the
  connected V1.14 keyboard, confirm the revised verdicts in
  [`unknown-commands.md`](unknown-commands.md) match live behavior.
  (Read-only.) Task #14.
- **Umbrella docs:** sync the three top-level summaries at
  `/home/user/src/ak820-experiments/{PROTOCOL.md,FIRMWARE-HACKING.md,
  RESEARCH.md}` with the new findings. Task #16.
- **Minor:** trace the actual chunked send for `local_364` in
  `FUN_00418420` past the excerpt cut (the keymap-data send call) — confirm
  exact chunk count and verify the 9 (from `local_50 = 9`) vs ~780-byte
  payload arithmetic. Side issue, not blocking.
- **Optional:** identify whether the Windows tool's `CMD 0x05 READ_ID` site
  reads `bcdDevice` and conditions on it. If yes, it would document the
  "skip CMD 0x11 on non-V1.13" branch we hypothesized.
- **Deferred:** USB-capture-based dynamic analysis of the Windows driver
  (explicitly out of scope per user). Could be used to verify the static
  analysis if there's ever a discrepancy.

## Commit log (this session)

```
docs: status — Phase 3-4 complete, keymap path identified  (this commit)
docs: windows driver analysis — actual CMD codes sent by vendor tool
docs: document VIA dual-mode variant (VID 0x3151 / PID 0x4021)
docs: cite 35ms timing source; capture lsusb + report descriptors
fix:  LCD chunk size is 4123 bytes, not 4096 (PROTOCOL.md)
docs: ghidra decompile of DeviceDriver.exe — HID call sites
feat: script for static analysis of vendor DeviceDriver.exe
docs: status update — Phase 1-3A complete, Phase 3B in flight
feat: Ghidra decompile of all 8 firmwares; document divergences
feat: cross-firmware dispatch table extractor and CMD coverage matrix
feat: Ghidra-based firmware analysis; refute "stub" hypothesis
feat: disassemble V1.13 helper functions for stub investigation
chore: add pefile/lief/pyghidra for Windows PE analysis
chore: gitignore vendor artifacts and ghidra project DBs
```

## Repository structure (current, ak820-re/)

```
ak820-re/
├── PROTOCOL.md                          — corrected (LCD 4123, VIA section, citations)
├── firmware-analysis.md                 — original (pre-Ghidra) dispatch notes
├── firmware-analysis-helpers.md         — Phase 1 helper-function semantics
├── unknown-commands.md                  — every verdict has Phase 1 + Phase 3 revisions
├── windows-driver-analysis.md           — Phase 3 vendor-tool analysis (this session's headline)
├── STATUS.md                            — this file
├── disassemble_handlers.py              — original handler disasm
├── disassemble_helpers.py               — helper disasm (Phase 1A)
├── extract_dispatch.py                  — pattern-based dispatch extractor (Phase 2A)
├── probe_commands.py                    — live read-only probing (Phase 14 pending)
├── probe_variants.py                    — variant probing
├── firmware-blobs/
│   ├── *.dispatch.{json,txt}            — per-blob dispatch dumps (8 × 2)
│   ├── diff.md                          — cross-blob CMD matrix
│   ├── findings.md                      — cross-blob narrative
│   └── cross-firmware-divergences.md    — per-blob handler diffs
├── ghidra-output/                       — Ghidra pseudo-C
│   ├── V1.13/{helpers,handlers}.md
│   ├── RS2_V1.28/handlers.md (× 6 more)
│   └── windows/{hid_calls,send_functions,setfeature_*,cmd_senders,strings}.md
├── ghidra-projects/                     — gitignored (large binary DBs)
├── scripts/ghidra/
│   ├── analyze_firmware.py              — firmware Ghidra script
│   ├── analyze_exe.py                   — Windows .exe Ghidra script
│   ├── analyze_all.sh                   — batch wrapper for 8 blobs
│   └── run-headless.sh                  — analyzeHeadless wrapper (legacy)
├── vendor/windows/                      — gitignored (vendor IP)
│   ├── AJAZZ_AK820Pro_driver_V1.0.0.5.rar.zip
│   ├── AK820Pro_V1.0.0.5.exe            — Inno Setup wrapper
│   └── extracted/app/
│       ├── DeviceDriver.exe             — main control utility (1.8 MB)
│       ├── mui.dll                      — side-loaded module
│       ├── config.xml                   — confirms VID/PID/features
│       └── layouts/rgb-keyboard.xml     — confirms 35 ms timing, macro support
├── dumps/
│   ├── *.bin / *.hex                    — live-probe results (prior session)
│   └── lsusb.txt                        — full HID descriptor (Phase 4B)
├── pyproject.toml                       — lief, pefile, pyghidra, capstone
└── .gitignore                           — vendor/, ghidra-projects/
```
