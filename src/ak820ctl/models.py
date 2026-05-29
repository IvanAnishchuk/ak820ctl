"""Pydantic models for AK820 keyboard settings."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 — used at runtime in save/load methods

from pydantic import BaseModel, Field


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
