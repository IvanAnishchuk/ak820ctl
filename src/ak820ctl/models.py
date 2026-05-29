"""Pydantic models for AK820 keyboard settings."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path  # noqa: TC003 — used at runtime in save/load methods

from pydantic import BaseModel, Field


class KeyName(StrEnum):
    """Valid key names for the AK820 keyboard (81 keys)."""

    ESC = "esc"
    F1 = "f1"
    F2 = "f2"
    F3 = "f3"
    F4 = "f4"
    F5 = "f5"
    F6 = "f6"
    F7 = "f7"
    F8 = "f8"
    F9 = "f9"
    F10 = "f10"
    F11 = "f11"
    F12 = "f12"
    GRAVE = "grave"
    N1 = "1"
    N2 = "2"
    N3 = "3"
    N4 = "4"
    N5 = "5"
    N6 = "6"
    N7 = "7"
    N8 = "8"
    N9 = "9"
    N0 = "0"
    MINUS = "minus"
    EQUAL = "equal"
    TAB = "tab"
    Q = "q"
    W = "w"
    E = "e"
    R = "r"
    T = "t"
    Y = "y"
    U = "u"
    I = "i"  # noqa: E741
    O = "o"  # noqa: E741
    P = "p"
    LBRACKET = "lbracket"
    RBRACKET = "rbracket"
    CAPS = "caps"
    A = "a"
    S = "s"
    D = "d"
    F = "f"
    G = "g"
    H = "h"
    J = "j"
    K = "k"
    L = "l"
    SEMICOLON = "semicolon"
    APOSTROPHE = "apostrophe"
    BACKSLASH = "backslash"
    LSHIFT = "lshift"
    Z = "z"
    X = "x"
    C = "c"
    V = "v"
    B = "b"
    N = "n"
    M = "m"
    COMMA = "comma"
    DOT = "dot"
    SLASH = "slash"
    RSHIFT = "rshift"
    ENTER = "enter"
    LCTRL = "lctrl"
    WIN = "win"
    LALT = "lalt"
    SPACE = "space"
    RALT = "ralt"
    FN = "fn"
    RCTRL = "rctrl"
    LEFT = "left"
    DOWN = "down"
    UP = "up"
    RIGHT = "right"
    BACKSPACE = "backspace"
    HOME = "home"
    PGUP = "pgup"
    DELETE = "delete"
    PGDN = "pgdn"


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


class KeyGroup(BaseModel):
    """A named group of keys sharing the same color."""

    name: str
    color: str = Field(pattern=r"^[0-9a-fA-F]{6}$")
    keys: list[KeyName]


class PerKeyConfig(BaseModel):
    """YAML-based per-key color configuration with named groups."""

    default: str = Field(default="000000", pattern=r"^[0-9a-fA-F]{6}$")
    groups: list[KeyGroup] = Field(default_factory=list)

    # TODO: add to_key_colors(keymap, num_keys) method.
    # Previous attempt called keymap.name_to_index() (which runs a dict
    # comprehension over all 144 entries) on every single key lookup inside
    # the inner loop — O(keys * 144) instead of O(keys + 144). Fix: call
    # name_to_index() once before the loop, store in a local variable.


class KeyMap(BaseModel):
    """Mapping of LED indices (0-143) to symbolic key names."""

    keys: dict[int, KeyName | None] = Field(default_factory=dict)

    def name_to_index(self) -> dict[KeyName, int]:
        """Build reverse mapping: key name -> index."""
        return {name: idx for idx, name in self.keys.items() if name is not None}

    def index_to_name(self) -> dict[int, KeyName]:
        """Build forward mapping: index -> key name (excluding nulls)."""
        return {idx: name for idx, name in self.keys.items() if name is not None}


class KeyboardDump(BaseModel):
    """Complete keyboard settings snapshot."""

    device: DeviceInfo = Field(default_factory=DeviceInfo)
    lighting: LightingConfig = Field(default_factory=LightingConfig)

    def save(self, path: Path) -> None:
        """Write to JSON file."""
        _ = path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> KeyboardDump:
        """Read from JSON file."""
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
