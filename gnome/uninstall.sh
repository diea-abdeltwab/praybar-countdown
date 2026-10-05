#!/usr/bin/env bash
# praybar - removes the extension, its settings and its caches.
set -euo pipefail

UUID="praybar@diea-abdeltwab.github.io"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/$UUID"

gnome-extensions disable "$UUID" 2>/dev/null || true
rm -rf "$DEST"
rm -rf "${XDG_CACHE_HOME:-$HOME/.cache}/praybar"
command -v dconf >/dev/null && dconf reset -f /org/gnome/shell/extensions/praybar/ || true
echo "✓ praybar removed (log out/in to fully unload it from the running shell)"
