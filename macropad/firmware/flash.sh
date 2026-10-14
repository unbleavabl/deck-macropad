#!/bin/sh
# Build and flash a keymap without touching the pad: ask the running firmware to jump to
# TinyUF2 over raw HID, wait for the drive, copy the image.
#   firmware/flash.sh [keymap]      (default: default)
# Only the default keymap answers the jump request; from `test` (or a broken build), hold
# both knob pushes for three seconds, or use the BOOT button / ST-Link (README, Flashing).
set -e
km=${1:-default}
here=$(cd "$(dirname "$0")" && pwd)
qmk compile -kb handwired/deck -km "$km" >/dev/null
if ! lsblk -o LABEL | grep -q STMF411BOOT; then
    python3 "$here/../host/deckd.py" boot
    for _ in $(seq 20); do lsblk -o LABEL | grep -q STMF411BOOT && break; sleep 0.5; done
fi
qmk flash -kb handwired/deck -km "$km" 2>&1 | tail -2
