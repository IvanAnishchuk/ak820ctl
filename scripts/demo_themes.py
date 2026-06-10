#!/usr/bin/env python3
"""Cycle through every shipped theme, switching the LCD image with each one.

For each `examples/perkey/<name>.json` (the compiled per-key colors), uploads
the matching `examples/lcd/<name>.png` to the LCD, writes the per-key colors,
and sleeps `INTERVAL_S` seconds before moving on.

Run from the repository root:

    uv run python scripts/demo_themes.py
"""

from __future__ import annotations

import time
from pathlib import Path

from pydantic import TypeAdapter

from ak820ctl.display import load_image, upload_image
from ak820ctl.models import KeyColor
from ak820ctl.perkey import NUM_KEYS, write_perkey

REPO_ROOT = Path(__file__).resolve().parent.parent
PERKEY_DIR = REPO_ROOT / "examples" / "perkey"
LCD_DIR = REPO_ROOT / "examples" / "lcd"
INTERVAL_S = 5
BRIGHTNESS = 5

_KEY_COLOR_LIST = TypeAdapter(list[KeyColor])


def load_perkey(path: Path) -> list[KeyColor]:
    entries = _KEY_COLOR_LIST.validate_json(path.read_bytes())
    keys = [KeyColor(index=i) for i in range(NUM_KEYS)]
    for entry in entries:
        keys[entry.index] = entry
    return keys


def main() -> None:
    themes = sorted(PERKEY_DIR.glob("*.json"))
    if not themes:
        msg = f"no themes found in {PERKEY_DIR}"
        raise SystemExit(msg)

    for theme_path in themes:
        name = theme_path.stem
        lcd_path = LCD_DIR / f"{name}.png"
        print(f"=== {name} ===")  # noqa: T201

        if lcd_path.exists():
            upload_image(load_image(lcd_path), slot=1)
        else:
            print(f"  (no LCD image at {lcd_path}, skipping image step)")  # noqa: T201

        write_perkey(load_perkey(theme_path), brightness=BRIGHTNESS)
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()  # noqa: T201
