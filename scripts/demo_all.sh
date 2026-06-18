#!/usr/bin/env bash
# Demo every ak820ctl feature against a connected AK820 keyboard.
#
# Walks the full CLI surface -- info, time, sleep, global light modes,
# custom per-key LED themes, and LCD image/GIF upload -- pausing between
# steps so each change is visible on the hardware. The keyboard's lighting
# and per-key buffer are snapshotted up front and restored on exit (the
# EXIT trap also fires if a step fails midway).
#
# Requires a connected AK820 (verify with `ak820ctl info`). Run from the
# repo root:
#
#     ./scripts/demo_all.sh
#
# Environment:
#     PAUSE       seconds to wait between visible steps (default 4)
#     BACKUP_DIR  directory for the state snapshots (default: a mktemp dir)
#
# NOTE: the LCD cannot be reset to the firmware clock screen
# programmatically -- press the keyboard's wheel button to restore it
# after the demo.

set -euo pipefail

PAUSE="${PAUSE:-4}"
BACKUP_DIR="${BACKUP_DIR:-$(mktemp -d -t ak820-demo.XXXXXX)}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
THEMES="$REPO_ROOT/src/ak820ctl/data/themes"
LAYOUTS="$REPO_ROOT/src/ak820ctl/data/layouts"
EXAMPLES="$REPO_ROOT/examples"

ak() { uv run ak820ctl "$@"; }
step() { printf '\n=== %s ===\n' "$*"; }

restore() {
    step "Restoring original per-key buffer and lighting"
    ak perkey --load "$BACKUP_DIR/backup-perkey.json" || true
    ak restore "$BACKUP_DIR/backup-state.json" || true
    printf 'Backups kept in: %s\n' "$BACKUP_DIR"
    printf 'NOTE: press the wheel button to restore the LCD clock screen.\n'
}

# --- preflight + backup ----------------------------------------------------
step "Device info"
ak info

step "Backing up current state to $BACKUP_DIR"
ak dump -o "$BACKUP_DIR/backup-state.json"
ak perkey --save "$BACKUP_DIR/backup-perkey.json"
trap restore EXIT

# --- time + sleep ----------------------------------------------------------
step "Sync clock to system time"
ak time

step "Sleep timer: 5min, then never"
ak sleep 5min
sleep "$PAUSE"
ak sleep never

# --- global light modes ----------------------------------------------------
step "Global light: static red"
ak light static -c ff0000 -b 5
sleep "$PAUSE"
step "Global light: breath blue"
ak light breath -c 0000ff -b 5 -S 3
sleep "$PAUSE"
step "Global light: spectrum rainbow"
ak light spectrum -r -b 5 -S 4
sleep "$PAUSE"
step "Global light: ripples green, scrolling right"
ak light ripples -c 00ff00 -d right -b 5
sleep "$PAUSE"

# --- custom per-key themes -------------------------------------------------
# Per-key colors only render while global mode is `custom`.
step "Switch to custom mode (required for per-key to render)"
ak light custom
sleep "$PAUSE"

for theme in groups-dracula groups-rainbow groups-gruvbox groups-cyberpunk; do
    step "Theme: $theme"
    ak theme-compile "$THEMES/$theme-theme.json" | ak perkey --load -
    sleep "$PAUSE"
done

step "Theme: rows-stealth (needs the perrow layout)"
ak theme-compile "$THEMES/rows-stealth-theme.json" --layout "$LAYOUTS/perrow.json" \
    | ak perkey --load -
sleep "$PAUSE"

# --- per-key direct controls ----------------------------------------------
step "Per-key: every key cyan"
ak perkey --all 00ffff -b 5
sleep "$PAUSE"
step "Per-key: paint individual keys (Esc/Q/W/E)"
ak perkey --key 0:ff0000 --key 17:ff8800 --key 18:ffff00 --key 19:00ff00 -b 5
sleep "$PAUSE"
step "Per-key: every key dim red (brightness 2)"
ak perkey --all ff0000 -b 2
sleep "$PAUSE"

# --- LCD image + gif -------------------------------------------------------
step "LCD: static image (bundled dracula smiley, resized to 128x128)"
ak image "$EXAMPLES/lcd/groups-dracula.png" --slot 1
sleep "$PAUSE"
step "LCD: animated GIF"
ak gif "$EXAMPLES/lcd/animation.gif" --slot 1
sleep "$PAUSE"

# Original state is reapplied by the EXIT trap (restore).
step "Demo complete"
