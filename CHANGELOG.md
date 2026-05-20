# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `image` / `gif` commands: upload static images and animated GIFs to the 128×128 LCD screen
- `perkey` command: read and set per-key custom RGB colors for 144 keys
- `dump` / `restore` commands: save and load keyboard settings as JSON
- Pydantic models for typed serialization/validation of keyboard settings
- `light --show` / `light` (no args): read and display current lighting config from keyboard
- `info` command: show device VID/PID and capabilities from CMD 0x05 response
- `send_report()`, `read_data()` HID helpers for read operations
- CLI commands: `time`, `light`, `sleep`, `info`
- USB HID protocol implementation for Ajazz AK820 (VID 0x0C45, PID 0x8009)
- Time sync, LED mode control (20 presets + custom), sleep timer
- Type stubs for hidapi C extension
- Hypothesis property-based tests for protocol packets
- Meson/ninja build orchestration (10 targets)
- Three type checkers: ty, mypy (strict), basedpyright (recommended)
- Mutation testing support (mutmut)
- Modular CI workflows with hardened runners and pinned action SHAs
- Security scaffolding: CodeQL, Scorecard, OSV scan, gitleaks, dependency review
- Supply-chain audit script (pip-audit + CycloneDX SBOM)
- Dependabot config (uv, pre-commit, github-actions ecosystems)
- Dependabot regen workflow for requirements*.txt sync
- Protocol documentation: COMMANDS.md, STATUS.md

### Changed

- `info` command: use CMD 0x05 for full device ID with LE uint16 firmware version (shows V1.20)

### Fixed

- LED color command: split into preamble + data payload (two-packet sequence)
- Replaced broad `except Exception` with specific `OSError` for HID errors
- Fixed firmware version display (`info` command)
- Eliminated double inter-command delay in `send_command()` (was sleeping in both `send_report()` and `send_command()`)
- Dependabot regen workflow trigger paths
