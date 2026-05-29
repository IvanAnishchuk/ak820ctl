#!/usr/bin/env python3
"""Generate example per-key color scheme JSON files.

Uses the LED keymap to place colors on the correct physical key indices.
Run from the repository root:

    python scripts/generate_examples.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
KEYMAP_PATH = REPO_ROOT / "src" / "ak820ctl" / "keymap.json"
OUTPUT_DIR = REPO_ROOT / "examples" / "perkey"
NUM_KEYS = 144

Color = tuple[int, int, int]


def load_keymap() -> dict[str, str | None]:
    return json.loads(KEYMAP_PATH.read_text())


def classify_keys(keymap: dict[str, str | None]) -> dict[str, set[str]]:
    """Group key indices (as strings) into semantic categories."""
    categories: dict[str, set[str]] = {
        "letters": set(),
        "numbers": set(),
        "fkeys": set(),
        "modifiers": set(),
        "arrows": set(),
        "nav": set(),
        "punct": set(),
        "mapped": set(),
    }

    modifier_names = {
        "lshift",
        "rshift",
        "lctrl",
        "rctrl",
        "lalt",
        "ralt",
        "win",
        "fn",
        "caps",
    }
    arrow_names = {"up", "down", "left", "right"}
    nav_names = {"home", "pgup", "pgdn", "delete", "backspace", "tab", "enter", "esc"}
    punct_names = {
        "grave",
        "minus",
        "equal",
        "lbracket",
        "rbracket",
        "backslash",
        "semicolon",
        "apostrophe",
        "comma",
        "dot",
        "slash",
        "space",
    }

    for idx, name in keymap.items():
        if name is None:
            continue
        categories["mapped"].add(idx)
        if len(name) == 1 and name.isalpha():
            categories["letters"].add(idx)
        elif name in "1234567890":
            categories["numbers"].add(idx)
        elif name.startswith("f") and name[1:].isdigit():
            categories["fkeys"].add(idx)
        elif name in modifier_names:
            categories["modifiers"].add(idx)
        elif name in arrow_names:
            categories["arrows"].add(idx)
        elif name in nav_names:
            categories["nav"].add(idx)
        elif name in punct_names:
            categories["punct"].add(idx)

    return categories


def make_scheme(
    color_map: list[tuple[set[str], Color]],
    default: Color = (0, 0, 0),
) -> list[dict[str, int]]:
    """Build a 144-entry key color list from category→color mappings."""
    keys = []
    for i in range(NUM_KEYS):
        si = str(i)
        r, g, b = default
        for indices, color in color_map:
            if si in indices:
                r, g, b = color
                break
        keys.append({"index": i, "r": r, "g": g, "b": b})
    return keys


def write_scheme(name: str, data: list[dict[str, int]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"  {path}")  # noqa: T201


def generate_all() -> None:
    keymap = load_keymap()
    cats = classify_keys(keymap)

    schemes: dict[str, list[tuple[set[str], Color]]] = {
        "ocean": [
            (cats["letters"], (0, 102, 204)),
            (cats["numbers"], (0, 128, 128)),
            (cats["fkeys"], (68, 136, 204)),
            (cats["modifiers"], (0, 51, 102)),
            (cats["arrows"], (0, 170, 204)),
            (cats["nav"], (0, 153, 204)),
            (cats["punct"], (51, 102, 153)),
        ],
        "sunset": [
            (cats["letters"], (255, 102, 0)),
            (cats["numbers"], (255, 170, 0)),
            (cats["fkeys"], (204, 51, 0)),
            (cats["modifiers"], (153, 0, 0)),
            (cats["arrows"], (255, 136, 0)),
            (cats["nav"], (255, 136, 0)),
            (cats["punct"], (204, 85, 0)),
        ],
        "stealth": [
            (cats["mapped"], (51, 26, 0)),
        ],
    }

    print("Generating example per-key color schemes:")  # noqa: T201
    for name, color_map in schemes.items():
        write_scheme(name, make_scheme(color_map))


if __name__ == "__main__":
    generate_all()
