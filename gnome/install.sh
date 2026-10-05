#!/usr/bin/env bash
# praybar - GNOME Shell extension installer (Fedora / any GNOME 45+).
# Copies the extension into your user directory and compiles its settings
# schema. No root needed. Safe to re-run (it replaces the previous copy).
set -euo pipefail

UUID="praybar@diea-abdeltwab.github.io"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$UUID"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/$UUID"

info()  { printf '\033[0;36m→\033[0m  %s\n' "$*"; }
ok()    { printf '\033[0;32m✓\033[0m  %s\n' "$*"; }
warn()  { printf '\033[1;33m⚠\033[0m  %s\n' "$*"; }
die()   { printf '\033[0;31m✗\033[0m  %s\n' "$*" >&2; exit 1; }

# ── 1. Dependencies ──────────────────────────────────────────
[ -d "$SRC" ] || die "Extension folder not found next to install.sh: $SRC"
command -v python3 >/dev/null || die "python3 not found (sudo dnf install python3)"
command -v glib-compile-schemas >/dev/null \
    || die "glib-compile-schemas not found. Find its package with: dnf provides '*/glib-compile-schemas'"

if command -v gnome-shell >/dev/null; then
    ok "GNOME Shell $(gnome-shell --version | awk '{print $3}') detected"
else
    warn "gnome-shell not found on PATH - installing anyway"
fi
command -v notify-send >/dev/null || warn "notify-send missing - will fall back to a plain shell notification (no 'Stop azan' button)"
if ! command -v mpv >/dev/null && ! command -v ffplay >/dev/null && ! command -v paplay >/dev/null && ! command -v pw-play >/dev/null; then
    warn "No audio player found - the azan will not play (sudo dnf install mpv)"
fi

# GeoClue (GNOME's location service). Its `where-am-i` tool gives a far better
# location than an IP lookup, which only knows your ISP's city. Optional: without
# it praybar falls back to IP geolocation.
have_where_am_i() {
    local p
    for p in /usr/libexec/geoclue-2.0/demos/where-am-i /usr/lib*/geoclue-2.0/demos/where-am-i /usr/lib/*/geoclue-2.0/demos/where-am-i; do
        [ -x "$p" ] && return 0
    done
    command -v where-am-i >/dev/null 2>&1
}

if have_where_am_i; then
    ok "GeoClue found (accurate location)"
else
    pkg_cmd=()
    if command -v dnf >/dev/null 2>&1; then
        pkg_cmd=(sudo dnf install -y geoclue2-demos)
    elif command -v apt-get >/dev/null 2>&1; then
        pkg_cmd=(sudo apt-get install -y geoclue-2-demo)
    fi
    warn "GeoClue's 'where-am-i' tool is missing - location would come from your IP address,"
    warn "which usually lands on your ISP's city instead of yours."
    if [ ${#pkg_cmd[@]} -gt 0 ]; then
        info "To fix it the installer will run:  ${pkg_cmd[*]}"
        ans=n
        [ -t 0 ] && read -r -p "   Install it now? [Y/n] " ans </dev/tty || true
        case "${ans:-Y}" in
            [Nn]*) warn "Skipped - using IP-based location" ;;
            *) if "${pkg_cmd[@]}"; then ok "GeoClue tool installed"; else warn "Install failed - using IP-based location"; fi ;;
        esac
    else
        warn "Install your distro's GeoClue demo package (it provides 'where-am-i'), then re-run this script."
    fi
fi

# ── 2. Copy ──────────────────────────────────────────────────
info "Installing to $DEST"
rm -rf "$DEST"
mkdir -p "$DEST"
cp -r "$SRC"/. "$DEST"/
chmod +x "$DEST/backend/praybar_backend.py"

# ── 3. Compile settings schema ───────────────────────────────
glib-compile-schemas "$DEST/schemas"
ok "Settings schema compiled"

# ── 4. Smoke-test the backend so problems show up now, not in the bar ──
if command -v gsettings >/dev/null 2>&1 && [ "$(gsettings get org.gnome.system.location enabled 2>/dev/null)" = "false" ]; then
    warn "GNOME Location Services is OFF - turn it on for an accurate location:"
    warn "Settings -> Privacy & Security -> Location Services"
fi
info "Testing the backend (needs internet, the first run can take ~15 s)..."
if out="$(python3 "$DEST/backend/praybar_backend.py" 2>/dev/null)" && grep -q '"ok": true' <<<"$out"; then
    ok "Backend works: $(python3 -c 'import json,sys; d=json.loads(sys.argv[1]); print(d["city"], "-", d["date"], "(via " + d["source"] + ")")' "$out")"
else
    warn "Backend test failed (offline?). The extension will retry once it is running."
fi

# ── 5. Enable ────────────────────────────────────────────────
if gnome-extensions enable "$UUID" 2>/dev/null; then
    ok "Enabled"
else
    warn "Could not enable yet - GNOME has not discovered the new extension."
fi

cat <<MSG

Done. One more step:
  • On Wayland (Fedora's default) GNOME only discovers new extensions at login:
      log out and back in, then run:  gnome-extensions enable $UUID
  • On X11 you can instead press Alt+F2, type  r  and press Enter.
Settings:  gnome-extensions prefs $UUID   (or click "Settings" in the bar menu)
MSG
