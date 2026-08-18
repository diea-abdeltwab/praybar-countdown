#!/usr/bin/env bash
# ============================================================
#  install.sh — praybar
#  Installs the prayer-times countdown module into waybar.
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
WAYBAR_DIR="$HOME/.config/waybar"
BACKUP_DIR="$WAYBAR_DIR/.praybar-backup"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

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
check_cmd waybar      "waybar"
check_cmd notify-send "libnotify"

# Audio player for azan
if command -v mpv &>/dev/null; then
    success "mpv found (audio player)"
elif command -v paplay &>/dev/null; then
    success "paplay found (audio player)"
else
    warn "No audio player found (mpv or paplay) — azan sound will not work"
    MISSING+=("mpv (optional)")
fi

# Wi-Fi positioning (accurate location, like Google/browsers use)
if command -v nmcli &>/dev/null || command -v iw &>/dev/null || command -v iwlist &>/dev/null; then
    success "Wi-Fi scan tool found (enables accurate Wi-Fi based location)"
else
    warn "No Wi-Fi scan tool found (nmcli, iw, or iwlist) — will fall back to less-accurate IP-based location"
    info "Install 'iw' (or NetworkManager) for street-level location accuracy"
fi

if [ ${#MISSING[@]} -gt 0 ]; then
    echo ""
    warn "Missing packages: ${MISSING[*]}"
    echo -e "    ${YELLOW}sudo pacman -S ${MISSING[*]}${RESET}"
    echo ""
    read -rp "Continue anyway? [y/N] " ans
    [[ "$ans" =~ ^[Yy]$ ]] || { error "Aborted."; exit 1; }
fi

# ─── 2. Backup existing waybar config ────────────────────
header "💾 Backing up current waybar config..."

mkdir -p "$BACKUP_DIR"

for f in "$WAYBAR_DIR/config.jsonc" "$WAYBAR_DIR/config" "$WAYBAR_DIR/style.css"; do
    if [ -f "$f" ]; then
        cp "$f" "$BACKUP_DIR/$(basename "$f").${TIMESTAMP}.bak"
        success "Backed up: $(basename "$f")"
    fi
done

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

# ─── 2c. Location preference ─────────────────────────────
header "📍 Location..."

MANUAL_LAT=""
MANUAL_LON=""
MANUAL_CITY=""
echo -e "  How should praybar figure out your location?"
echo -e "    ${CYAN}1)${RESET} Auto-detect (Wi-Fi positioning, falls back to IP-based)"
echo -e "    ${CYAN}2)${RESET} Enter exact coordinates manually (recommended if this machine"
echo -e "       has no Wi-Fi adapter — auto-detect can't work without one)"
read -rp "  Choice [1/2, default 1]: " loc_choice
if [[ "$loc_choice" == "2" ]]; then
    echo -e "  ${CYAN}Tip:${RESET} search '<your city> coordinates' online, or use Google Maps"
    echo -e "  (right-click your location → the numbers shown are lat, lon)."
    read -rp "  Latitude  (e.g. 29.3084): " MANUAL_LAT
    read -rp "  Longitude (e.g. 30.8428): " MANUAL_LON
    read -rp "  City label to show in the tooltip (e.g. Fayoum, EG): " MANUAL_CITY
    success "Manual location set: ${MANUAL_LAT}, ${MANUAL_LON} (${MANUAL_CITY:-unlabeled})"
else
    success "Auto-detect enabled"
fi

# ─── 3. Copy module files ────────────────────────────────
header "📁 Copying files..."

mkdir -p "$WAYBAR_DIR"

cp "$APP_DIR/praybar.py" "$WAYBAR_DIR/praybar.py"
sed -i "s/^TIME_FORMAT[[:space:]]*=.*/TIME_FORMAT          = \"$TIME_FORMAT\"/" "$WAYBAR_DIR/praybar.py"
if [[ -n "$MANUAL_LAT" && -n "$MANUAL_LON" ]]; then
    sed -i "s/^MANUAL_LATITUDE[[:space:]]*=.*/MANUAL_LATITUDE  = $MANUAL_LAT/"   "$WAYBAR_DIR/praybar.py"
    sed -i "s/^MANUAL_LONGITUDE[[:space:]]*=.*/MANUAL_LONGITUDE = $MANUAL_LON/" "$WAYBAR_DIR/praybar.py"
    sed -i "s/^MANUAL_CITY[[:space:]]*=.*/MANUAL_CITY      = \"$MANUAL_CITY\"/" "$WAYBAR_DIR/praybar.py"
fi
chmod +x "$WAYBAR_DIR/praybar.py"
success "praybar.py → $WAYBAR_DIR/"

mkdir -p "$WAYBAR_DIR/assets"
cp "$APP_DIR/assets/praybar-style.css" "$WAYBAR_DIR/assets/praybar-style.css"
success "assets/praybar-style.css → $WAYBAR_DIR/assets/"

# ─── 4. Patch waybar config + style.css ──────────────────
header "⚙️  Patching waybar config..."

python3 "$APP_DIR/scripts/patch_waybar.py" add

# Keep config and config.jsonc in sync
if [ -f "$WAYBAR_DIR/config.jsonc" ] && [ -f "$WAYBAR_DIR/config" ]; then
    if grep -q "custom/praybar" "$WAYBAR_DIR/config.jsonc" 2>/dev/null; then
        cp "$WAYBAR_DIR/config.jsonc" "$WAYBAR_DIR/config"
        success "Synced config.jsonc → config"
    else
        cp "$WAYBAR_DIR/config" "$WAYBAR_DIR/config.jsonc"
        success "Synced config → config.jsonc"
    fi
fi

# ─── 5. Azan audio file ──────────────────────────────────
header "🔊 Azan audio file..."

AZAN_DEST="$WAYBAR_DIR/azan.mp3"

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

# ─── 6. Daily refresh timer (runs at 12:00) ──────────────
header "⏰ Installing daily refresh timer..."

SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
if command -v systemctl &>/dev/null; then
    mkdir -p "$SYSTEMD_USER_DIR"
    cp "$APP_DIR/systemd/praybar-refresh.service" "$SYSTEMD_USER_DIR/"
    cp "$APP_DIR/systemd/praybar-refresh.timer"   "$SYSTEMD_USER_DIR/"
    systemctl --user daemon-reload
    systemctl --user enable --now praybar-refresh.timer
    success "Daily refresh timer installed (fires every day at 12:00)"
else
    warn "systemctl not found — skipping daily refresh timer (waybar's own polling will still keep times updated)"
fi

# ─── 7. Restart waybar ───────────────────────────────────
header "🔄 Restarting waybar..."

if pgrep -x waybar &>/dev/null; then
    pkill waybar 2>/dev/null || true
    sleep 0.5
    nohup waybar &>/dev/null &
    disown
    success "waybar restarted"
else
    warn "waybar is not running — start it manually: waybar &"
fi

# ─── 8. Quick test ───────────────────────────────────────
header "🧪 Testing module..."

output=$(python3 "$WAYBAR_DIR/praybar.py" 2>/dev/null || echo '{"text":"error"}')
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
echo -e "    $WAYBAR_DIR/praybar.py"
echo -e "    $WAYBAR_DIR/assets/praybar-style.css"
echo ""
echo -e "  ${CYAN}Time format:${RESET}"
echo -e "    $TIME_FORMAT  (change anytime: edit TIME_FORMAT in praybar.py)"
echo ""
echo -e "  ${CYAN}Location:${RESET}"
if [[ -n "$MANUAL_LAT" && -n "$MANUAL_LON" ]]; then
    echo -e "    Manual — ${MANUAL_LAT}, ${MANUAL_LON} (${MANUAL_CITY:-unlabeled})"
else
    echo -e "    Auto-detect (Wi-Fi, falls back to IP-based)"
fi
echo ""
echo -e "  ${CYAN}Azan audio:${RESET}"
echo -e "    $AZAN_DEST"
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
