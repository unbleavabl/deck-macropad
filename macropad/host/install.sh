#!/bin/sh
# Install deckd as a systemd user service (runs whenever you're logged into Hyprland).
set -e
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p ~/.config/deckd ~/.config/systemd/user
[ -e ~/.config/deckd/config.toml ] || cp "$here/config.toml" ~/.config/deckd/config.toml
cp "$here/deckd.service" ~/.config/systemd/user/deckd.service
systemctl --user daemon-reload
systemctl --user enable --now deckd
systemctl --user --no-pager status deckd | head -5
