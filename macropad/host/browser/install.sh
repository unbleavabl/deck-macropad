#!/bin/sh
# Register the native messaging host for Chromium and Chrome. Then load the extension once:
# chrome://extensions -> Developer mode -> Load unpacked -> this folder's extension/
set -e
here=$(cd "$(dirname "$0")" && pwd)
for dir in ~/.config/chromium ~/.config/google-chrome; do
    [ -d "$dir" ] || continue
    mkdir -p "$dir/NativeMessagingHosts"
    cat > "$dir/NativeMessagingHosts/com.deckd.bridge.json" <<J
{
  "name": "com.deckd.bridge",
  "description": "deckd tab volume bridge",
  "path": "$here/deckd_bridge.py",
  "type": "stdio",
  "allowed_origins": ["chrome-extension://cjdicppidaifmeebppjoediccbnanlbj/"]
}
J
    echo "registered in $dir"
done
echo "Now load $here/extension in chrome://extensions (Developer mode, Load unpacked)."
