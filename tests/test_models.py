"""Tests for pydantic models that don't fit elsewhere.

Currently pins the per-instance isolation behaviour of mutable defaults
on `ThemeSource` and `KeyboardDump` — we switched from
`Field(default_factory=...)` to plain `= {}` / `= DeviceInfo()` literals
and rely on pydantic v2 deep-copying them for each model instance.
"""

from __future__ import annotations

from ak820ctl.keys import Key
from ak820ctl.models import KeyboardDump, ThemeSource


def test_theme_source_default_dicts_are_per_instance() -> None:
    a = ThemeSource()
    b = ThemeSource()
    assert a.groups is not b.groups
    assert a.overrides is not b.overrides
    a.groups["letters"] = "#ff0000"
    a.overrides[Key.q] = "#00ff00"
    assert b.groups == {}
    assert b.overrides == {}


def test_keyboard_dump_default_submodels_are_per_instance() -> None:
    a = KeyboardDump()
    b = KeyboardDump()
    assert a.device is not b.device
    assert a.lighting is not b.lighting
    a.device.firmware = "v1.20"
    a.lighting.mode = "custom"
    assert b.device.firmware == "unknown"
    assert b.lighting.mode == "off"
