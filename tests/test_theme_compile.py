"""Unit tests for theme compile helpers and ThemeSource model."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ak820ctl.cli import compile_theme, load_layout
from ak820ctl.keys import KEY_INDEX, NUM_KEYS, Key
from ak820ctl.models import KeyColor, ThemeSource

REPO_ROOT = Path(__file__).resolve().parent.parent
THEMES_DIR = REPO_ROOT / "src" / "ak820ctl" / "data" / "themes"
LAYOUTS_DIR = REPO_ROOT / "src" / "ak820ctl" / "data" / "layouts"
COMPILED_DIR = REPO_ROOT / "examples" / "perkey"


SIMPLE_LAYOUT: dict[str, list[Key]] = {
    "letters": [Key.q, Key.w, Key.e],
    "nav": [Key.left],
}


# ---------------------------- Key enum ----------------------------


def test_key_enum_has_144_members() -> None:
    assert len(Key) == NUM_KEYS
    assert len(KEY_INDEX) == NUM_KEYS


def test_key_index_matches_keymap_json() -> None:
    assert KEY_INDEX[Key.esc] == 1
    assert KEY_INDEX[Key.space] == 94
    assert KEY_INDEX[Key.q] == 38
    assert KEY_INDEX[Key.m] == 80
    assert KEY_INDEX[Key.idx_0] == 0
    assert KEY_INDEX[Key.idx_143] == 143


def test_key_index_values_are_full_permutation() -> None:
    assert set(KEY_INDEX.values()) == set(range(NUM_KEYS))


# ---------------------------- load_layout ----------------------------


def test_load_layout_bundled_simple_has_expected_groups() -> None:
    layout = load_layout()
    assert "letters" in layout
    assert "f_keys" in layout
    assert "space" in layout
    assert Key.q in layout["letters"]


def test_load_layout_from_path(tmp_path: Path) -> None:
    data = {"row1": ["q", "w"], "row2": ["esc"]}
    p = tmp_path / "layout.json"
    _ = p.write_text(json.dumps(data), encoding="utf-8")
    layout = load_layout(p)
    assert layout == {"row1": [Key.q, Key.w], "row2": [Key.esc]}


def test_load_layout_rejects_unknown_key_name(tmp_path: Path) -> None:
    data = {"letters": ["q", "phantom"]}
    p = tmp_path / "layout.json"
    _ = p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValidationError, match="phantom"):
        _ = load_layout(p)


# ---------------------------- ThemeSource ----------------------------


def test_theme_source_defaults() -> None:
    ts = ThemeSource()
    assert ts.base == "#000000"
    assert ts.groups == {}
    assert ts.overrides == {}


def test_theme_source_accepts_well_formed_hex() -> None:
    ts = ThemeSource(base="#ff0000", groups={"x": "#00FF00"})
    assert ts.base == "#ff0000"
    assert ts.groups["x"] == "#00FF00"


def test_theme_source_rejects_hex_without_hash() -> None:
    with pytest.raises(ValidationError):
        _ = ThemeSource(base="ff0000")


def test_theme_source_rejects_short_hex() -> None:
    with pytest.raises(ValidationError):
        _ = ThemeSource(base="#fff")


def test_theme_source_rejects_long_hex() -> None:
    with pytest.raises(ValidationError):
        _ = ThemeSource(base="#ff0000ff")


def test_theme_source_rejects_non_hex_chars() -> None:
    with pytest.raises(ValidationError):
        _ = ThemeSource(base="#xy0000")


def test_theme_source_rejects_non_string_hex() -> None:
    with pytest.raises(ValidationError):
        _ = ThemeSource.model_validate({"base": 12345})


def test_theme_source_overrides_coerces_strings_to_key() -> None:
    ts = ThemeSource.model_validate_json('{"overrides": {"esc": "#ff0000"}}')
    assert ts.overrides == {Key.esc: "#ff0000"}


def test_theme_source_overrides_rejects_unknown_key_name() -> None:
    with pytest.raises(ValidationError, match="not_a_key"):
        _ = ThemeSource.model_validate({"overrides": {"not_a_key": "#ff0000"}})


# ---------------------------- compile_theme ----------------------------


def test_compile_all_base_when_empty_groups_and_overrides() -> None:
    src = ThemeSource(base="#010203")
    keys = compile_theme(src, SIMPLE_LAYOUT)
    assert len(keys) == NUM_KEYS
    assert all(k.r == 1 and k.g == 2 and k.b == 3 for k in keys)


def test_compile_default_base_is_black() -> None:
    src = ThemeSource(groups={"letters": "#ff0000"})
    keys = compile_theme(src, SIMPLE_LAYOUT)
    assert keys[0] == KeyColor(index=0, r=0, g=0, b=0)
    assert keys[1] == KeyColor(index=1, r=0, g=0, b=0)
    assert keys[KEY_INDEX[Key.q]] == KeyColor(index=KEY_INDEX[Key.q], r=255, g=0, b=0)
    assert keys[KEY_INDEX[Key.w]] == KeyColor(index=KEY_INDEX[Key.w], r=255, g=0, b=0)
    assert keys[KEY_INDEX[Key.e]] == KeyColor(index=KEY_INDEX[Key.e], r=255, g=0, b=0)


def test_compile_groups_apply_to_listed_keys() -> None:
    src = ThemeSource(groups={"letters": "#00ff00", "nav": "#0000ff"})
    keys = compile_theme(src, SIMPLE_LAYOUT)
    assert keys[KEY_INDEX[Key.q]].g == 255
    assert keys[KEY_INDEX[Key.left]].b == 255


def test_compile_overrides_win_over_groups() -> None:
    src = ThemeSource(
        groups={"letters": "#00ff00"},
        overrides={Key.q: "#ffffff"},
    )
    keys = compile_theme(src, SIMPLE_LAYOUT)
    assert keys[KEY_INDEX[Key.q]] == KeyColor(index=KEY_INDEX[Key.q], r=255, g=255, b=255)
    assert keys[KEY_INDEX[Key.w]] == KeyColor(index=KEY_INDEX[Key.w], r=0, g=255, b=0)


def test_compile_overrides_win_over_base() -> None:
    src = ThemeSource(base="#010101", overrides={Key.esc: "#ffffff"})
    keys = compile_theme(src, SIMPLE_LAYOUT)
    assert keys[KEY_INDEX[Key.esc]] == KeyColor(index=KEY_INDEX[Key.esc], r=255, g=255, b=255)
    assert keys[0] == KeyColor(index=0, r=1, g=1, b=1)


def test_compile_groups_not_listed_stay_at_base() -> None:
    src = ThemeSource(base="#abcdef", groups={"letters": "#112233"})
    keys = compile_theme(src, SIMPLE_LAYOUT)
    assert keys[KEY_INDEX[Key.left]] == KeyColor(index=KEY_INDEX[Key.left], r=0xAB, g=0xCD, b=0xEF)


def test_compile_unknown_group_raises_with_name() -> None:
    src = ThemeSource(groups={"bogus_group": "#ff0000"})
    with pytest.raises(ValueError, match="bogus_group"):
        _ = compile_theme(src, SIMPLE_LAYOUT)


def test_compile_overrides_reach_unnamed_idx_slots() -> None:
    src = ThemeSource(overrides={Key.idx_0: "#ff00ff", Key.idx_14: "#00ffff"})
    keys = compile_theme(src, SIMPLE_LAYOUT)
    assert keys[0] == KeyColor(index=0, r=255, g=0, b=255)
    assert keys[14] == KeyColor(index=14, r=0, g=255, b=255)


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
    layout = load_layout(layout_path)
    keys = compile_theme(source, layout)

    compiled = json.dumps([k.model_dump() for k in keys], indent=2) + "\n"
    expected = expected_path.read_text(encoding="utf-8")
    assert compiled == expected, f"{theme_name} compile output differs from {expected_path.name}"
