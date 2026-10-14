#!/usr/bin/env bash
# Install the slider helper as a user service that starts with your session.
set -euo pipefail
cd "$(dirname "$0")"
install -Dm755 macropad_sliders.py ~/.local/bin/macropad_sliders.py
[ -f ~/.config/macropad/sliders.toml ] || install -Dm644 sliders.toml ~/.config/macropad/sliders.toml
install -Dm644 macropad-sliders.service ~/.config/systemd/user/macropad-sliders.service
systemctl --user daemon-reload
systemctl --user enable --now macropad-sliders.service
echo "Running. Edit ~/.config/macropad/sliders.toml, then: systemctl --user restart macropad-sliders"
echo "Logs: journalctl --user -u macropad-sliders -f"
