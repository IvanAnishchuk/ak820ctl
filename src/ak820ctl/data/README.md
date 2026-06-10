# Per-key theme data

This directory holds the canonical data for the per-key theme system:

- `keymap.json` — index→name mapping for the 144 LED slots, consumed at import
  time by `ak820ctl/keys.py` to build `KEY_INDEX`. The static counterpart is the
  `Key` enum (every entry here must be a `Key` member; drift fails import).
  Slots without a physical key use placeholder names `idx_0`, `idx_14`, ...,
  `idx_143` so they remain addressable from theme `overrides`. Not user-
  overridable at runtime.
- `layouts/` — JSON files that group key names into named groups. Two ship:
  - `layouts/simple.json` — 8 groups (letters / f_keys / digits / punctuation /
    wrappers / modifiers / space / nav). Used by `groups-*-theme.json` sources.
  - `layouts/perrow.json` — 16 groups with per-row letter/wrapper/punctuation
    variants (e.g. `letters_qwerty`, `letters_asdf`, `letters_zxcv`). Used by
    `rows-*-theme.json` sources.
- `themes/` — **theme source files** in the high-level format described below.
  Filenames follow the pattern `{zoning}-{name}-theme.json` where zoning is
  either `groups` (simple layout, unified letter color) or `rows` (perrow
  layout, per-row letter shades). The `-theme` suffix distinguishes source
  files from the compiled per-key outputs.

Compiled outputs (consumed by `ak820ctl perkey --load`) drop the `-theme`
suffix and live in `examples/perkey/` — e.g. the source
`themes/groups-solarized-theme.json` compiles to
`examples/perkey/groups-solarized.json`.

The LED buffer is laid out as **8 rows × 18 columns**; only the first 6 rows hold
physical keys. The rest are non-key LEDs or unused slots — reachable only via
the `indices` field of a theme source.

## Theme source format

```json
{
  "base": "#000000",
  "groups": {
    "letters": "#0066cc",
    "f_keys": "#00ff00"
  },
  "overrides": {
    "esc": "#ff0000",
    "space": "#ffffff",
    "idx_0": "#ff0000",
    "idx_14": "#0015ff"
  }
}
```

- `base` (default `"#000000"`): fallback for every slot.
- `groups`: group-name → hex. Group names must exist in the chosen layout.
  Applied on top of `base`.
- `overrides`: `Key` enum name → hex. Wins over `groups` and `base` for that
  specific slot. Every one of the 144 slots has a name in `keymap.json`,
  including buffer gaps and the firmware-locked underglow slots 128-143
  (named `idx_<N>`), so any slot is addressable here.
- All hex strings: **`#RRGGBB`** — leading `#` is required and only 6 hex
  digits are accepted (validated by the `HexColor` type).

## Compile and load

```bash
# Compile a source to stdout (simple layout is the default)
ak820ctl theme-compile src/ak820ctl/data/themes/groups-solarized-theme.json

# Write to a file; pastel/row themes need --layout perrow.json
ak820ctl theme-compile src/ak820ctl/data/themes/rows-pastel-turquoise-theme.json \
  --layout src/ak820ctl/data/layouts/perrow.json \
  -o my-turquoise.json

# Pipe directly into perkey --load
ak820ctl theme-compile src/ak820ctl/data/themes/groups-nord-theme.json | \
  ak820ctl perkey --load /dev/stdin --brightness 5
```

Per-key colors only display when lighting mode is `custom` (which `perkey --load`
sets at the end of its write). If you change to a different mode via the
keyboard's Fn shortcuts, run `ak820ctl light custom --brightness 5` to switch
back.

## Shipped themes

Source files in `themes/`:

| Source | Layout | Description |
|---|---|---|
| `groups-basic-theme.json` | simple | Minimal 7-color primary palette (R/O/Y/G/C/B/M). |
| `groups-alt-theme.json` | simple | Alternative 7-color basic palette (hue shifted ~30°: chartreuse/spring/turquoise/azure/violet/rose/gold). |
| `groups-solarized-theme.json` | simple | Authentic Solarized 8-accent palette (Ethan Schoonover). |
| `groups-nord-theme.json` | simple | Nord palette (Arctic Code Studio): frost blues + aurora accents. |
| `groups-gruvbox-theme.json` | simple | Gruvbox retro: warm earth tones (yellow letters as in the original theme). |
| `groups-dracula-theme.json` | simple | Dracula editor theme: vibrant purple/cyan/pink accents. |
| `groups-cyberpunk-theme.json` | simple | Synthwave/neon: hot pink, electric cyan, neon green. |
| `groups-monokai-theme.json` | simple | Classic Monokai editor palette (pink letters, lime green, cyan). |
| `groups-rainbow-theme.json` | simple | Rainbow gradient — uses `indices` for all 144 slots. |
| `rows-pastel-turquoise-theme.json` | perrow | Turquoise letter rows + warm accents (see scheme below). |
| `rows-pastel-sunset-theme.json` | perrow | Sunset palette with cool complementary accents. |
| `rows-pastel-ocean-theme.json` | perrow | Ocean palette with warm complementary accents. |
| `rows-pastel-forest-theme.json` | perrow | Sage green letter rows + warm earthy accents. |
| `rows-stealth-theme.json` | perrow | Dim warm-brown variations across rows — very low light. |

Pre-compiled outputs of each of these live in `examples/perkey/` (same names
without the `-theme` suffix) for direct `perkey --load` use without re-running
the compile step.

## Zoning scheme (used by the bundled layouts and themes)

Both pastel files share the same **horizontal sub-zoning within each row**. The
idea is: every typing row has letters (the "main" content), structural keys
that wrap the row (tab, caps, enter, shifts) and punctuation keys mixed in.
Coloring each role distinctly makes the layout readable while keeping rows
visually grouped.

| Group | Keys | Role |
|---|---|---|
| F-keys | F1-F12 | row-0 main |
| Esc, Del | esc, delete | row-0 accent (complementary to F-keys) |
| Digits | 1-0 | row-1 main |
| `` ` `` `-` `=` | grave, minus, equal | row-1 accent (complementary to digits) |
| **QWERTY letters** | Q-P | row-2 main |
| tab, `\` | tab, backslash | row-2 wrappers (same shade) |
| `[` `]` | brackets | row-2 punctuation (same spectrum as other rows' punctuation, different shade) |
| **ASDF letters** | A-L | row-3 main |
| caps, enter | caps, enter | row-3 wrappers |
| `;` `'` | semicolon, apostrophe | row-3 punctuation |
| **ZXCV letters** | Z-M | row-4 main |
| lshift, rshift | shifts | row-4 wrappers |
| `,` `.` `/` | comma, dot, slash | row-4 punctuation |
| Modifiers | ctrl/win/alt/fn | row-5 main |
| Space | space | row-5 standalone |
| Nav | arrows, backspace, home, pgup, pgdn | distinct cluster |

Each of the three letter rows uses a **slightly different shade of the main
color** so rows are subtly distinguishable. The wrappers within each row also
shift shade to match their row's letters.

## `groups-pastel-turquoise.json` palette (turquoise main, warm accents)

| Group | RGB |
|---|---|
| F-keys | light blue `(80, 180, 255)` |
| Esc + Del | yellow `(255, 230, 30)` |
| Digits 1-0 | lime `(100, 255, 60)` |
| `` ` `` `-` `=` | hot pink `(255, 80, 180)` |
| QWERTY letters | cyan-turquoise `(0, 240, 220)` |
| QWERTY tab, `\` | orange `(255, 130, 40)` |
| QWERTY `[` `]` | raspberry `(255, 50, 110)` |
| ASDF letters | mid-turquoise `(0, 255, 170)` |
| ASDF caps, enter | orange `(255, 150, 30)` |
| ASDF `;` `'` | raspberry `(230, 60, 100)` |
| ZXCV letters | sea-turquoise `(60, 220, 130)` |
| ZXCV shifts | orange `(255, 170, 40)` |
| ZXCV `,` `.` `/` | raspberry `(220, 70, 130)` |
| Modifiers | coral red `(255, 60, 80)` |
| Space | cool white `(200, 220, 240)` |
| Nav | violet `(150, 50, 255)` |

## `groups-pastel-sunset.json` palette (sunset main, cool complementary accents)

| Group | RGB |
|---|---|
| F-keys | gold `(255, 170, 0)` |
| Esc + Del | indigo `(60, 60, 200)` |
| Digits 1-0 | amber `(255, 136, 0)` |
| `` ` `` `-` `=` | blue-violet `(80, 100, 230)` |
| QWERTY letters | bright orange `(255, 102, 0)` |
| QWERTY tab, `\` | teal `(0, 200, 220)` |
| QWERTY `[` `]` | blue `(60, 150, 240)` |
| ASDF letters | deep orange `(204, 85, 0)` |
| ASDF caps, enter | green-teal `(0, 180, 180)` |
| ASDF `;` `'` | sky blue `(80, 170, 230)` |
| ZXCV letters | red-orange `(204, 51, 0)` |
| ZXCV shifts | cyan `(0, 200, 240)` |
| ZXCV `,` `.` `/` | deep blue `(40, 130, 230)` |
| Modifiers | dark wine `(153, 0, 0)` |
| Space | warm cream `(255, 220, 180)` |
| Nav | night purple-blue `(80, 40, 200)` |

## `groups-pastel-ocean.json` palette (ocean main, warm complementary accents)

| Group | RGB |
|---|---|
| F-keys | bright sky `(0, 170, 230)` |
| Esc + Del | gold `(255, 180, 50)` |
| Digits 1-0 | aqua `(0, 153, 204)` |
| `` ` `` `-` `=` | coral `(255, 130, 80)` |
| QWERTY letters | ocean blue `(0, 102, 204)` |
| QWERTY tab, `\` | peach `(255, 160, 80)` |
| QWERTY `[` `]` | salmon `(255, 120, 130)` |
| ASDF letters | deep blue `(51, 102, 153)` |
| ASDF caps, enter | amber `(255, 170, 50)` |
| ASDF `;` `'` | coral `(255, 110, 100)` |
| ZXCV letters | navy `(0, 51, 102)` |
| ZXCV shifts | gold `(255, 150, 30)` |
| ZXCV `,` `.` `/` | deep coral `(220, 90, 70)` |
| Modifiers | teal `(0, 128, 128)` |
| Space | sea foam `(180, 230, 240)` |
| Nav | sandy gold `(255, 180, 80)` |

## `groups-pastel-forest.json` palette (sage main, earthy accents)

| Group | RGB |
|---|---|
| F-keys | pale sky `(180, 220, 240)` |
| Esc + Del | deep berry `(150, 50, 100)` |
| Digits 1-0 | butter yellow `(240, 220, 100)` |
| `` ` `` `-` `=` | wisteria `(180, 130, 200)` |
| QWERTY letters | light sage `(150, 200, 110)` |
| QWERTY tab, `\` | honey `(220, 160, 50)` |
| QWERTY `[` `]` | terracotta `(220, 110, 80)` |
| ASDF letters | medium sage `(120, 180, 90)` |
| ASDF caps, enter | amber `(210, 140, 40)` |
| ASDF `;` `'` | clay `(200, 95, 75)` |
| ZXCV letters | deep moss `(90, 150, 70)` |
| ZXCV shifts | warm brown `(180, 110, 40)` |
| ZXCV `,` `.` `/` | rust `(180, 80, 60)` |
| Modifiers | dark wood brown `(110, 80, 50)` |
| Space | pale cream/birch `(240, 230, 200)` |
| Nav | lavender `(150, 110, 200)` |

## Notes on the LED hardware

- The R channel in the per-key LEDs reads back at ~2/3 of the stored value
  (e.g. `255` displays roughly as `168`), while G and B render closer to full.
  Highly desaturated pastels (e.g. `#ffdab9`) lose their warm cast — they read
  more cyan/green. The schemes above are tuned around this: warm hues use
  high R with low G/B, and "pastel" effects come from saturation choice rather
  than from washing out with R+G+B all high.
- Slots **128-143 are firmware-locked** at `#ffffff` and ignore per-key writes.
  They're likely the side/underglow LEDs, controlled by the standard lighting
  mode rather than the per-key command.
