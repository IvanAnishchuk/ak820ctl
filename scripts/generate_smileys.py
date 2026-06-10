#!/usr/bin/env python3
"""Generate one 128x128 smiley face PNG per shipped theme.

Each theme gets a distinct facial expression rendered with PIL primitives,
colored to evoke that theme's signature palette. Output goes to
`examples/lcd/<theme-name>.png` and is used by the LCD demo script.

Run from the repository root:

    uv run python scripts/generate_smileys.py
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

if TYPE_CHECKING:
    from collections.abc import Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "examples" / "lcd"
SIZE = 128

# Each theme: (face_fill, feature_color, bg_color, expression)
THEMES: dict[str, tuple[str, str, str, str]] = {
    "groups-basic": ("#ffe000", "#000000", "#003090", "classic"),
    "groups-alt": ("#ffcc44", "#3a1f5d", "#0a0a14", "happy"),
    "groups-solarized": ("#fdf6e3", "#073642", "#002b36", "neutral"),
    "groups-nord": ("#88c0d0", "#2e3440", "#1a1f2a", "sleepy"),
    "groups-gruvbox": ("#fabd2f", "#3c3836", "#282828", "tongue"),
    "groups-dracula": ("#bd93f9", "#282a36", "#191a21", "sly"),
    "groups-cyberpunk": ("#ff00ff", "#00ffff", "#0a0014", "cool"),
    "groups-monokai": ("#a6e22e", "#272822", "#191919", "grin"),
    "groups-rainbow": ("#ffd000", "#202020", "#000000", "heart_eyes"),
    "rows-pastel-turquoise": ("#00f0dc", "#ff5078", "#0a1a1c", "wink"),
    "rows-pastel-sunset": ("#ff6600", "#3c3cc8", "#1a0e00", "surprised"),
    "rows-pastel-ocean": ("#3399cc", "#ffa050", "#001020", "kiss"),
    "rows-pastel-forest": ("#96c86e", "#dc9028", "#101a08", "angel"),
    "rows-stealth": ("#5a3010", "#231408", "#080404", "sleepy"),
}


def _heart(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color: str) -> None:
    d.ellipse((cx - r, cy - r, cx, cy), fill=color)
    d.ellipse((cx, cy - r, cx + r, cy), fill=color)
    d.polygon([(cx - r, cy - 1), (cx + r, cy - 1), (cx, cy + r + 2)], fill=color)


def _zs(d: ImageDraw.ImageDraw, color: str) -> None:
    # Two stacked "Z" glyphs as line segments in the top-right corner.
    for ox, oy, s in ((86, 14, 10), (102, 28, 7)):
        d.line((ox, oy, ox + s, oy), fill=color, width=2)
        d.line((ox + s, oy, ox, oy + s), fill=color, width=2)
        d.line((ox, oy + s, ox + s, oy + s), fill=color, width=2)


def _dot_eye(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color: str) -> None:
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)


def _closed_eye(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color: str) -> None:
    d.line((cx - r, cy, cx + r, cy), fill=color, width=4)


def _arc_eye(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color: str) -> None:
    """^ shape — happy closed eye."""
    d.arc((cx - r, cy - r, cx + r, cy + r), 200, 340, fill=color, width=4)


def _smile(d: ImageDraw.ImageDraw, color: str, width: int = 4) -> None:
    d.arc((36, 60, 92, 100), 0, 180, fill=color, width=width)


_LE_X, _RE_X, _EYE_Y, _EYE_R = 42, 86, 52, 7


def _draw_classic(d: ImageDraw.ImageDraw, face: str, feature: str) -> None:
    del face
    _dot_eye(d, _LE_X, _EYE_Y, _EYE_R, feature)
    _dot_eye(d, _RE_X, _EYE_Y, _EYE_R, feature)
    _smile(d, feature)


def _draw_wink(d: ImageDraw.ImageDraw, face: str, feature: str) -> None:
    del face
    _dot_eye(d, _LE_X, _EYE_Y, _EYE_R, feature)
    _closed_eye(d, _RE_X, _EYE_Y, _EYE_R, feature)
    _smile(d, feature)


def _draw_grin(d: ImageDraw.ImageDraw, face: str, feature: str) -> None:
    _dot_eye(d, _LE_X, _EYE_Y, _EYE_R, feature)
    _dot_eye(d, _RE_X, _EYE_Y, _EYE_R, feature)
    d.rounded_rectangle((36, 76, 92, 104), radius=10, fill=feature)
    d.line((36, 84, 92, 84), fill=face, width=2)


def _draw_surprised(d: ImageDraw.ImageDraw, face: str, feature: str) -> None:
    del face
    _dot_eye(d, _LE_X, _EYE_Y, _EYE_R, feature)
    _dot_eye(d, _RE_X, _EYE_Y, _EYE_R, feature)
    d.ellipse((54, 76, 74, 100), fill=feature)


def _draw_tongue(d: ImageDraw.ImageDraw, face: str, feature: str) -> None:
    del face
    _dot_eye(d, _LE_X, _EYE_Y, _EYE_R, feature)
    _dot_eye(d, _RE_X, _EYE_Y, _EYE_R, feature)
    _smile(d, feature)
    d.rounded_rectangle((56, 86, 74, 108), radius=6, fill="#ff5577")


def _draw_cool(d: ImageDraw.ImageDraw, face: str, feature: str) -> None:
    del face
    d.rectangle((22, 48, 106, 56), fill=feature)
    d.ellipse((24, 42, 56, 64), fill=feature)
    d.ellipse((72, 42, 104, 64), fill=feature)
    _smile(d, feature)


def _draw_happy(d: ImageDraw.ImageDraw, face: str, feature: str) -> None:
    del face
    _arc_eye(d, _LE_X, _EYE_Y, 12, feature)
    _arc_eye(d, _RE_X, _EYE_Y, 12, feature)
    _smile(d, feature)


def _draw_heart_eyes(d: ImageDraw.ImageDraw, face: str, feature: str) -> None:
    del face
    _heart(d, _LE_X, _EYE_Y, 10, feature)
    _heart(d, _RE_X, _EYE_Y, 10, feature)
    _smile(d, feature)


def _draw_sly(d: ImageDraw.ImageDraw, face: str, feature: str) -> None:
    del face
    _closed_eye(d, _LE_X, _EYE_Y, _EYE_R, feature)
    _closed_eye(d, _RE_X, _EYE_Y, _EYE_R, feature)
    d.arc((52, 70, 96, 100), 0, 180, fill=feature, width=4)


def _draw_sleepy(d: ImageDraw.ImageDraw, face: str, feature: str) -> None:
    del face
    _closed_eye(d, _LE_X, _EYE_Y, _EYE_R, feature)
    _closed_eye(d, _RE_X, _EYE_Y, _EYE_R, feature)
    d.arc((50, 78, 78, 94), 0, 180, fill=feature, width=3)
    _zs(d, feature)


def _draw_angel(d: ImageDraw.ImageDraw, face: str, feature: str) -> None:
    del face
    d.ellipse((38, 4, 90, 18), outline="#ffe080", width=3)
    _dot_eye(d, _LE_X, _EYE_Y, _EYE_R, feature)
    _dot_eye(d, _RE_X, _EYE_Y, _EYE_R, feature)
    _smile(d, feature)


def _draw_neutral(d: ImageDraw.ImageDraw, face: str, feature: str) -> None:
    del face
    _dot_eye(d, _LE_X, _EYE_Y, _EYE_R, feature)
    _dot_eye(d, _RE_X, _EYE_Y, _EYE_R, feature)
    d.line((40, 86, 88, 86), fill=feature, width=4)


def _draw_kiss(d: ImageDraw.ImageDraw, face: str, feature: str) -> None:
    del face
    _arc_eye(d, _LE_X, _EYE_Y, 10, feature)
    _arc_eye(d, _RE_X, _EYE_Y, 10, feature)
    _heart(d, 64, 88, 10, feature)


_EXPRESSIONS: dict[str, Callable[[ImageDraw.ImageDraw, str, str], None]] = {
    "classic": _draw_classic,
    "wink": _draw_wink,
    "grin": _draw_grin,
    "surprised": _draw_surprised,
    "tongue": _draw_tongue,
    "cool": _draw_cool,
    "happy": _draw_happy,
    "heart_eyes": _draw_heart_eyes,
    "sly": _draw_sly,
    "sleepy": _draw_sleepy,
    "angel": _draw_angel,
    "neutral": _draw_neutral,
    "kiss": _draw_kiss,
}


def draw_smiley(expr: str, face: str, feature: str, bg: str) -> Image.Image:
    img = Image.new("RGB", (SIZE, SIZE), bg)
    d = ImageDraw.Draw(img)
    pad = 6
    d.ellipse((pad, pad, SIZE - pad, SIZE - pad), fill=face)

    handler = _EXPRESSIONS.get(expr)
    if handler is None:
        msg = f"unknown expression {expr!r}"
        raise ValueError(msg)
    handler(d, face, feature)
    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, (face, feature, bg, expr) in THEMES.items():
        img = draw_smiley(expr, face, feature, bg)
        path = OUT_DIR / f"{name}.png"
        img.save(path)
        print(f"  {path}")  # noqa: T201


if __name__ == "__main__":
    main()
