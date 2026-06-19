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
#     SLOT        LCD slot to overwrite (default 1)
#
# WHAT IS *NOT* RESTORED -- the protocol can only write these, not read
# them, so the demo cannot back them up or put them back:
#   - Sleep timer: left at `never`. If you had a non-default timeout,
#     re-set it afterwards with `ak820ctl sleep <value>`.
#   - LCD slot $SLOT: overwritten and unrecoverable. Press the keyboard's
#     wheel button for the firmware clock screen, or re-upload your own
#     image with `ak820ctl image <file> --slot $SLOT`.

set -euo pipefail

PAUSE="${PAUSE:-4}"
BACKUP_DIR="${BACKUP_DIR:-$(mktemp -d -t ak820-demo.XXXXXX)}"
SLOT="${SLOT:-1}"
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
    printf '\n'
    printf 'NOT auto-restored (protocol has no read-back for these):\n'
    printf '  - Sleep timer left at never -- re-set if needed with: ak820ctl sleep <value>\n'
    printf '  - LCD slot %s overwritten -- press the wheel button, or: ak820ctl image <file> --slot %s\n' \
        "$SLOT" "$SLOT"
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

# The original sleep timer can't be read back, so it can't be restored --
# the demo leaves it at `never` and the exit note flags this.
step "Sleep timer: 5min, then never (original value can't be restored)"
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
# LCD content is write-only: slot $SLOT is overwritten and cannot be backed
# up or restored. Point the demo at a different slot with the SLOT env var.
printf '\n!!! LCD slot %s will be overwritten and CANNOT be restored.\n' "$SLOT"
printf '    Set SLOT=<n> to target a different slot. Continuing in 3s...\n'
sleep 3
step "LCD: static image to slot $SLOT (bundled dracula smiley, resized to 128x128)"
ak image "$EXAMPLES/lcd/groups-dracula.png" --slot "$SLOT"
sleep "$PAUSE"
step "LCD: animated GIF to slot $SLOT"
ak gif "$EXAMPLES/lcd/animation.gif" --slot "$SLOT"
sleep "$PAUSE"

# Original state is reapplied by the EXIT trap (restore).
step "Demo complete"
