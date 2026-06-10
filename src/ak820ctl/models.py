"""Pydantic models for AK820 keyboard settings."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 — used at runtime in save/load methods
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from ak820ctl.keys import Key  # noqa: TC001 — used at runtime in ThemeSource field type

# Strict CSS-style hex color: `#` plus exactly 6 hex digits (case-insensitive).
HexColor = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]


class DeviceInfo(BaseModel):
    """Device identity from CMD 0x05."""

    vid: int = 0
    pid: int = 0
    firmware: str = "unknown"
    firmware_raw: int = 0
    capabilities: int = 0


class LightingConfig(BaseModel):
    """Lighting state from CMD 0x12."""

    mode: str = "off"
    mode_value: int = 0
    r: int = Field(default=255, ge=0, le=255)
    g: int = Field(default=255, ge=0, le=255)
    b: int = Field(default=255, ge=0, le=255)
    rainbow: bool = False
    brightness: int = Field(default=5, ge=0, le=5)
    speed: int = Field(default=3, ge=0, le=5)
    direction: str = "left"


class KeyColor(BaseModel):
    """Single key color entry for per-key custom lighting."""

    index: int = Field(ge=0, le=143)
    r: int = Field(default=0, ge=0, le=255)
    g: int = Field(default=0, ge=0, le=255)
    b: int = Field(default=0, ge=0, le=255)


class ThemeSource(BaseModel):
    """Source for a theme: base color, per-group colors, per-key overrides.

    Compiled by `theme-compile` into a 144-entry list of `KeyColor`. All colors
    are strict `#RRGGBB` hex (case-insensitive, leading `#` required). Group
    names must exist in the chosen layout; override names must be `Key` members.
    Slots without a physical key are addressable as `idx_<N>` in `overrides`
    (e.g. `idx_0`, `idx_14`, ..., `idx_143`). Order of precedence: base →
    groups → overrides.
    """

    base: HexColor = "#000000"
    groups: dict[str, HexColor] = {}
    overrides: dict[Key, HexColor] = {}


class KeyboardDump(BaseModel):
    """Complete keyboard settings snapshot."""

    device: DeviceInfo = DeviceInfo()
    lighting: LightingConfig = LightingConfig()

    def save(self, path: Path) -> None:
        """Write to JSON file."""
        _ = path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> KeyboardDump:
        """Read from JSON file."""
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
