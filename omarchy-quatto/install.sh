#!/usr/bin/env bash
# ============================================================
#  install.sh — praybar (Omarchy 4 "Quattro" / Quickshell)
#  Installs the prayer-times countdown as a custom command
#  module in the Omarchy 4 bar (~/.config/omarchy/shell.json).
# ============================================================
set -euo pipefail

# ─── Colors ──────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}→${RESET}  $*"; }
success() { echo -e "${GREEN}✓${RESET}  $*"; }
warn()    { echo -e "${YELLOW}⚠${RESET}  $*"; }
error()   { echo -e "${RED}✗${RESET}  $*"; }
header()  { echo -e "\n${BOLD}$*${RESET}"; }

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OMARCHY_CFG="$HOME/.config/omarchy"
BAR_SCRIPTS_DIR="$OMARCHY_CFG/bar/scripts"
SHELL_JSON="$OMARCHY_CFG/shell.json"
BACKUP_DIR="$OMARCHY_CFG/.praybar-backup"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

# ─── 0. Sanity check: is this actually Omarchy 4? ────────
header "🔎 Checking this looks like Omarchy 4 (Quattro)..."

if [ -d "$HOME/.config/waybar" ] && [ ! -f "$SHELL_JSON" ] && ! command -v omarchy &>/dev/null; then
    warn "Found ~/.config/waybar but no shell.json/omarchy CLI — this looks like Omarchy 3."
    warn "You probably want ../linux/install.sh (the Waybar version) instead."
    read -rp "  Continue with the Omarchy 4 installer anyway? [y/N] " force_ans
    [[ "$force_ans" =~ ^[Yy]$ ]] || { error "Aborted."; exit 1; }
fi
success "Proceeding with the Omarchy 4 / Quickshell install"

# ─── 1. Check dependencies ───────────────────────────────
header "🔍 Checking dependencies..."

check_cmd() {
    local cmd=$1 pkg=$2
    if command -v "$cmd" &>/dev/null; then
        success "$cmd found"
    else
        warn "$cmd not found — install: $pkg"
        MISSING+=("$pkg")
    fi
}

MISSING=()
check_cmd python3     "python3"

# Audio player for azan
if command -v mpv &>/dev/null; then
    success "mpv found (audio player)"
elif command -v paplay &>/dev/null; then
    success "paplay found (audio player)"
else
    warn "No audio player found (mpv or paplay) — azan sound will not work"
    MISSING+=("mpv (optional)")
fi

# Notifications — Omarchy 4's shell absorbs Mako's job as the
# freedesktop notification daemon, so notify-send should keep working
# unchanged; we just check it's on disk.
check_cmd notify-send "libnotify"

if [ ${#MISSING[@]} -gt 0 ]; then
    echo ""
    warn "Missing packages: ${MISSING[*]}"
    echo -e "    ${YELLOW}sudo pacman -S ${MISSING[*]}${RESET}"
    echo ""
    read -rp "Continue anyway? [y/N] " ans
    [[ "$ans" =~ ^[Yy]$ ]] || { error "Aborted."; exit 1; }
fi

# ─── 2. Backup existing shell.json ───────────────────────
header "💾 Backing up current shell.json (if any)..."

mkdir -p "$BACKUP_DIR"
if [ -f "$SHELL_JSON" ]; then
    cp "$SHELL_JSON" "$BACKUP_DIR/shell.json.${TIMESTAMP}.bak"
    success "Backed up: shell.json"
else
    info "No existing shell.json — one will be seeded from Omarchy's defaults"
fi
echo "$TIMESTAMP" > "$BACKUP_DIR/last_install.txt"
success "Backup saved to: $BACKUP_DIR"

# ─── 2b. Time format preference ──────────────────────────
header "🕐 Time format..."

TIME_FORMAT="24h"
echo -e "  How should prayer times be displayed in the tooltip?"
echo -e "    ${CYAN}1)${RESET} 24-hour  (e.g. 13:05)"
echo -e "    ${CYAN}2)${RESET} 12-hour  (e.g. 1:05 PM)"
read -rp "  Choice [1/2, default 1]: " fmt_choice
if [[ "$fmt_choice" == "2" ]]; then
    TIME_FORMAT="12h"
fi
success "Time format set to: $TIME_FORMAT"

# ─── 2c. Location ────────────────────────────────────────
header "📍 Location..."
info "Detected automatically from your network and re-detected every night"
info "at 00:00 together with that day's prayer times — nothing to configure."

# ─── 3. Copy module files ────────────────────────────────
header "📁 Copying files..."

mkdir -p "$BAR_SCRIPTS_DIR"

cp "$APP_DIR/praybar.py" "$BAR_SCRIPTS_DIR/praybar.py"
sed -i "s/^TIME_FORMAT[[:space:]]*=.*/TIME_FORMAT          = \"$TIME_FORMAT\"/" "$BAR_SCRIPTS_DIR/praybar.py"
chmod +x "$BAR_SCRIPTS_DIR/praybar.py"
success "praybar.py → $BAR_SCRIPTS_DIR/"

# ─── 3b. Show the detected location ──────────────────────
header "📍 Detecting your location..."
info "This can take a few seconds..."
DETECTED="$(python3 "$BAR_SCRIPTS_DIR/praybar.py" 2>/dev/null | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('tooltip', '').splitlines()[0].replace('🕌  Prayer Times — ', '').replace('🕌 Prayer Times — ', ''))
except Exception:
    print('')
" 2>/dev/null)"
if [[ -n "$DETECTED" && "$DETECTED" != Could* ]]; then
    success "Detected: ${DETECTED}"
else
    warn "Could not detect your location right now (offline?). It will be retried automatically."
fi

# ─── 4. Patch shell.json ─────────────────────────────────
header "⚙️  Patching ~/.config/omarchy/shell.json..."

if python3 "$APP_DIR/scripts/patch_shell_json.py" add; then
    :
else
    error "Could not patch shell.json — see message above."
    error "You can add the module by hand; see omarchy-quatto/README.md → 'Manual setup'."
    exit 1
fi

# ─── 5. Azan audio file ──────────────────────────────────
header "🔊 Azan audio file..."

AZAN_DEST="$BAR_SCRIPTS_DIR/azan.mp3"

if [ -f "$AZAN_DEST" ]; then
    success "azan.mp3 already in place"
elif [ -f "$APP_DIR/assets/azan.mp3" ]; then
    cp "$APP_DIR/assets/azan.mp3" "$AZAN_DEST"
    success "azan.mp3 copied from app folder"
else
    info "Trying to download azan audio..."
    AZAN_URLS=(
        "https://cdn.islamic.network/quran/audio/128/ar.alafasy/adhan.mp3"
        "https://download.quranicaudio.com/quran/mishaari_raashid_al_3afaasee/001.mp3"
    )
    downloaded=false
    if command -v curl &>/dev/null || command -v wget &>/dev/null; then
        for url in "${AZAN_URLS[@]}"; do
            if command -v curl &>/dev/null; then
                curl -fsSL --max-time 15 "$url" -o "$AZAN_DEST" 2>/dev/null && downloaded=true && break
            else
                wget -q --timeout=15 "$url" -O "$AZAN_DEST" 2>/dev/null && downloaded=true && break
            fi
        done
    fi

    if $downloaded && [ -s "$AZAN_DEST" ]; then
        success "azan.mp3 downloaded"
    else
        rm -f "$AZAN_DEST"
        warn "Could not download azan.mp3 automatically."
        info "Place any azan mp3 file at: $AZAN_DEST"
        info "Example:"
        echo -e "    ${CYAN}cp /path/to/azan.mp3 $AZAN_DEST${RESET}"
        info "A fallback system beep will be used until then."
    fi
fi

# ─── 6. Daily refresh timer (runs at 00:00) ──────────────
header "⏰ Installing daily refresh timer..."

SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
if command -v systemctl &>/dev/null; then
    mkdir -p "$SYSTEMD_USER_DIR"
    cp "$APP_DIR/systemd/praybar-refresh.service" "$SYSTEMD_USER_DIR/"
    cp "$APP_DIR/systemd/praybar-refresh.timer"   "$SYSTEMD_USER_DIR/"
    systemctl --user daemon-reload
    systemctl --user enable --now praybar-refresh.timer
    success "Daily refresh timer installed (fires every day at 00:00)"
else
    warn "systemctl not found — skipping daily refresh timer (the bar's own polling will still keep times updated)"
fi

# ─── 7. Reload the Omarchy shell ─────────────────────────
header "🔄 Reloading the Omarchy shell..."

if command -v omarchy-shell &>/dev/null && omarchy-shell shell reloadConfig &>/dev/null; then
    success "Sent reloadConfig to the running shell (shell.json re-read live)"
elif command -v omarchy-restart-shell &>/dev/null; then
    omarchy-restart-shell &>/dev/null || true
    success "Restarted the Omarchy shell (omarchy-restart-shell)"
else
    warn "Could not reload automatically — log out/in, or run:"
    echo -e "    ${CYAN}omarchy-shell shell reloadConfig${RESET}   (live reload)"
    echo -e "    ${CYAN}omarchy-restart-shell${RESET}              (full shell restart)"
fi

# ─── 8. Quick test ───────────────────────────────────────
header "🧪 Testing module..."

output=$(python3 "$BAR_SCRIPTS_DIR/praybar.py" 2>/dev/null || echo '{"text":"error"}')
if echo "$output" | grep -q '"text"'; then
    text=$(echo "$output" | python3 -c "import sys,json; print(json.load(sys.stdin)['text'])" 2>/dev/null || echo "?")
    success "Module output: $text"
else
    warn "Unexpected output — check your internet connection and try again"
fi

# ─── Summary ─────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}════════════════════════════════════════${RESET}"
echo -e "${BOLD}${GREEN}  ✅ Installation complete!${RESET}"
echo -e "${BOLD}${GREEN}════════════════════════════════════════${RESET}"
echo ""
echo -e "  ${CYAN}Files installed:${RESET}"
echo -e "    $BAR_SCRIPTS_DIR/praybar.py"
echo -e "    $AZAN_DEST"
echo ""
echo -e "  ${CYAN}Bar config:${RESET}"
echo -e "    $SHELL_JSON  (custom command module: \"praybar\")"
echo ""
echo -e "  ${CYAN}Time format:${RESET}"
echo -e "    $TIME_FORMAT  (change anytime: edit TIME_FORMAT in praybar.py)"
echo ""
echo -e "  ${CYAN}Location:${RESET}"
echo -e "    Automatic — re-detected every night at 00:00"
echo ""
echo -e "  ${CYAN}Backup saved at:${RESET}"
echo -e "    $BACKUP_DIR/"
echo ""
echo -e "  ${YELLOW}Note: Notification dismiss requires notify-send ≥ 0.8${RESET}"
echo -e "  ${YELLOW}(libnotify 0.8+ supports --wait and --action flags)${RESET}"
echo ""
echo -e "  ${YELLOW}To uninstall:${RESET}"
echo -e "    ./uninstall.sh"
echo ""
