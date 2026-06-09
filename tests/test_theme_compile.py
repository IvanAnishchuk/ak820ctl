"""Unit tests for theme compile helpers and ThemeSource model."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ak820ctl.cli import _compile_theme, _load_keymap, _load_layout
from ak820ctl.models import KeyColor, ThemeSource
from ak820ctl.perkey import NUM_KEYS

REPO_ROOT = Path(__file__).resolve().parent.parent
THEMES_DIR = REPO_ROOT / "src" / "ak820ctl" / "data" / "themes"
LAYOUTS_DIR = REPO_ROOT / "src" / "ak820ctl" / "data" / "layouts"
COMPILED_DIR = REPO_ROOT / "examples" / "perkey"


# Minimal layout + keymap fixtures used by most unit tests
SIMPLE_KEYMAP = {"esc": 1, "q": 38, "w": 39, "e": 40, "space": 94, "left": 99}
SIMPLE_LAYOUT = {
    "letters": ["q", "w", "e"],
    "nav": ["left"],
}


# ---------------------------- _load_keymap ----------------------------


def test_load_keymap_bundled_returns_known_names() -> None:
    km = _load_keymap()
    assert km["esc"] == 1
    assert km["space"] == 94
    assert km["q"] == 38
    assert km["m"] == 80


def test_load_keymap_skips_null_entries(tmp_path: Path) -> None:
    raw = {"0": None, "1": "esc", "2": None, "3": "f1"}
    p = tmp_path / "km.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    km = _load_keymap(p)
    assert km == {"esc": 1, "f1": 3}


def test_load_keymap_inverts_index_to_name(tmp_path: Path) -> None:
    raw = {"5": "x", "9": "y"}
    p = tmp_path / "km.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    km = _load_keymap(p)
    assert km == {"x": 5, "y": 9}


# ---------------------------- _load_layout ----------------------------


def test_load_layout_bundled_simple_has_expected_groups() -> None:
    layout = _load_layout()
    assert "letters" in layout
    assert "f_keys" in layout
    assert "space" in layout
    assert "q" in layout["letters"]


def test_load_layout_from_path(tmp_path: Path) -> None:
    data = {"row1": ["a", "b"], "row2": ["c"]}
    p = tmp_path / "layout.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    layout = _load_layout(p)
    assert layout == data


# ---------------------------- ThemeSource ----------------------------


def test_theme_source_defaults() -> None:
    ts = ThemeSource()
    assert ts.base == "#000000"
    assert ts.groups == {}
    assert ts.overrides == {}
    assert ts.indices == {}


def test_theme_source_accepts_well_formed_hex() -> None:
    ts = ThemeSource(base="#ff0000", groups={"x": "#00FF00"})
    assert ts.base == "#ff0000"
    assert ts.groups["x"] == "#00FF00"


def test_theme_source_rejects_hex_without_hash() -> None:
    with pytest.raises(ValidationError):
        ThemeSource(base="ff0000")


def test_theme_source_rejects_short_hex() -> None:
    with pytest.raises(ValidationError):
        ThemeSource(base="#fff")


def test_theme_source_rejects_long_hex() -> None:
    with pytest.raises(ValidationError):
        ThemeSource(base="#ff0000ff")


def test_theme_source_rejects_non_hex_chars() -> None:
    with pytest.raises(ValidationError):
        ThemeSource(base="#xy0000")


def test_theme_source_rejects_non_string_hex() -> None:
    with pytest.raises(ValidationError):
        ThemeSource.model_validate({"base": 12345})


def test_theme_source_indices_parses_stringified_int_keys() -> None:
    """JSON forces string keys; pydantic should coerce them to int."""
    ts = ThemeSource.model_validate_json('{"indices": {"5": "#ff0000"}}')
    assert ts.indices == {5: "#ff0000"}


def test_theme_source_indices_rejects_non_integer_string_keys() -> None:
    with pytest.raises(ValidationError):
        ThemeSource.model_validate_json('{"indices": {"abc": "#ff0000"}}')


# ---------------------------- _compile_theme ----------------------------


def test_compile_all_base_when_empty_groups_and_overrides() -> None:
    src = ThemeSource(base="#010203")
    keys = _compile_theme(src, SIMPLE_LAYOUT, SIMPLE_KEYMAP)
    assert len(keys) == NUM_KEYS
    assert all(k.r == 1 and k.g == 2 and k.b == 3 for k in keys)


def test_compile_default_base_is_black() -> None:
    src = ThemeSource(groups={"letters": "#ff0000"})
    keys = _compile_theme(src, SIMPLE_LAYOUT, SIMPLE_KEYMAP)
    # All non-letter indices stay black
    assert keys[0] == KeyColor(index=0, r=0, g=0, b=0)
    assert keys[1] == KeyColor(index=1, r=0, g=0, b=0)
    # letters become red
    assert keys[38] == KeyColor(index=38, r=255, g=0, b=0)
    assert keys[39] == KeyColor(index=39, r=255, g=0, b=0)
    assert keys[40] == KeyColor(index=40, r=255, g=0, b=0)


def test_compile_groups_apply_to_listed_keys() -> None:
    src = ThemeSource(groups={"letters": "#00ff00", "nav": "#0000ff"})
    keys = _compile_theme(src, SIMPLE_LAYOUT, SIMPLE_KEYMAP)
    assert keys[38].g == 255
    assert keys[99].b == 255


def test_compile_overrides_win_over_groups() -> None:
    src = ThemeSource(
        groups={"letters": "#00ff00"},
        overrides={"q": "#ffffff"},
    )
    keys = _compile_theme(src, SIMPLE_LAYOUT, SIMPLE_KEYMAP)
    # q is in 'letters' but explicitly overridden
    assert keys[38] == KeyColor(index=38, r=255, g=255, b=255)
    # other letters keep group color
    assert keys[39] == KeyColor(index=39, r=0, g=255, b=0)


def test_compile_overrides_win_over_base() -> None:
    src = ThemeSource(base="#010101", overrides={"esc": "#ffffff"})
    keys = _compile_theme(src, SIMPLE_LAYOUT, SIMPLE_KEYMAP)
    assert keys[1] == KeyColor(index=1, r=255, g=255, b=255)
    # neighbours stay at base
    assert keys[0] == KeyColor(index=0, r=1, g=1, b=1)


def test_compile_groups_not_listed_stay_at_base() -> None:
    src = ThemeSource(base="#abcdef", groups={"letters": "#112233"})
    keys = _compile_theme(src, SIMPLE_LAYOUT, SIMPLE_KEYMAP)
    # nav group not specified, so nav keys remain at base
    assert keys[99] == KeyColor(index=99, r=0xAB, g=0xCD, b=0xEF)


def test_compile_unknown_group_raises_with_name() -> None:
    src = ThemeSource(groups={"bogus_group": "#ff0000"})
    with pytest.raises(ValueError, match="bogus_group"):
        _compile_theme(src, SIMPLE_LAYOUT, SIMPLE_KEYMAP)


def test_compile_unknown_override_raises_with_name() -> None:
    src = ThemeSource(overrides={"not_a_key": "#ff0000"})
    with pytest.raises(ValueError, match="not_a_key"):
        _compile_theme(src, SIMPLE_LAYOUT, SIMPLE_KEYMAP)


def test_compile_group_with_unknown_key_in_layout_raises() -> None:
    layout = {"letters": ["q", "phantom"]}
    src = ThemeSource(groups={"letters": "#ff0000"})
    with pytest.raises(ValueError, match="phantom"):
        _compile_theme(src, layout, SIMPLE_KEYMAP)


def test_compile_indices_apply_by_index() -> None:
    src = ThemeSource(indices={5: "#ff0000", 100: "#00ff00"})
    keys = _compile_theme(src, SIMPLE_LAYOUT, SIMPLE_KEYMAP)
    assert keys[5] == KeyColor(index=5, r=255, g=0, b=0)
    assert keys[100] == KeyColor(index=100, r=0, g=255, b=0)


def test_compile_indices_win_over_overrides_and_groups() -> None:
    src = ThemeSource(
        groups={"letters": "#00ff00"},
        overrides={"q": "#0000ff"},
        indices={38: "#ffffff"},  # 38 = q
    )
    keys = _compile_theme(src, SIMPLE_LAYOUT, SIMPLE_KEYMAP)
    assert keys[38] == KeyColor(index=38, r=255, g=255, b=255)


def test_compile_indices_reach_unnamed_slots() -> None:
    """Slots without symbolic names (idx 0, 14-18, etc.) are reachable via indices."""
    src = ThemeSource(indices={0: "#ff00ff", 14: "#00ffff"})
    keys = _compile_theme(src, SIMPLE_LAYOUT, SIMPLE_KEYMAP)
    assert keys[0] == KeyColor(index=0, r=255, g=0, b=255)
    assert keys[14] == KeyColor(index=14, r=0, g=255, b=255)


def test_compile_index_out_of_range_raises() -> None:
    src = ThemeSource(indices={144: "#ff0000"})
    with pytest.raises(ValueError, match="out of range"):
        _compile_theme(src, SIMPLE_LAYOUT, SIMPLE_KEYMAP)


# ---------------------- Byte-identical regeneration ----------------------


def _theme_layout(theme_name: str) -> str:
    """Theme name prefix determines layout: 'rows-...' → perrow, else simple."""
    return "perrow" if theme_name.startswith("rows-") else "simple"


SHIPPED_THEMES = sorted(p.stem.removesuffix("-theme") for p in THEMES_DIR.glob("*-theme.json"))


@pytest.mark.parametrize("theme_name", SHIPPED_THEMES)
def test_shipped_theme_regenerates_byte_identical(theme_name: str) -> None:
    """Every theme source compiles to the matching examples/perkey/ file exactly."""
    source_path = THEMES_DIR / f"{theme_name}-theme.json"
    layout_path = LAYOUTS_DIR / f"{_theme_layout(theme_name)}.json"
    expected_path = COMPILED_DIR / f"{theme_name}.json"

    source = ThemeSource.model_validate_json(source_path.read_text(encoding="utf-8"))
    keymap = _load_keymap()
    layout = _load_layout(layout_path)
    keys = _compile_theme(source, layout, keymap)

    compiled = json.dumps([k.model_dump() for k in keys], indent=2) + "\n"
    expected = expected_path.read_text(encoding="utf-8")
    assert compiled == expected, f"{theme_name} compile output differs from {expected_path.name}"
