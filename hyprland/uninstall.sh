#!/usr/bin/env bash
# ============================================================
#  uninstall.sh — praybar
#  Removes the praybar module and restores the original config.
# ============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}→${RESET}  $*"; }
success() { echo -e "${GREEN}✓${RESET}  $*"; }
warn()    { echo -e "${YELLOW}⚠${RESET}  $*"; }
error()   { echo -e "${RED}✗${RESET}  $*"; }
header()  { echo -e "\n${BOLD}$*${RESET}"; }

WAYBAR_DIR="$HOME/.config/waybar"
BACKUP_DIR="$WAYBAR_DIR/.praybar-backup"

# ─── Confirm ─────────────────────────────────────────────
echo -e "${BOLD}${RED}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║   🗑️  Uninstall praybar          ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${RESET}"
echo "  This will:"
echo "  • Remove praybar.py from waybar config dir"
echo "  • Remove praybar CSS from style.css"
echo "  • Remove the module entry from config"
echo "  • Optionally restore your pre-install backup"
echo ""
read -rp "  Are you sure? [y/N] " ans
[[ "$ans" =~ ^[Yy]$ ]] || { info "Aborted — nothing was changed."; exit 0; }

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── Offer backup restore ────────────────────────────────
RESTORE_BACKUP=false
if [ -d "$BACKUP_DIR" ] && ls "$BACKUP_DIR"/*.bak &>/dev/null 2>&1; then
    echo ""
    warn "Found backup files from the original install:"
    ls -lh "$BACKUP_DIR"/*.bak 2>/dev/null | awk '{print "   " $NF " (" $5 ")"}'
    echo ""
    read -rp "  Restore these backups instead of patching? [y/N] " restore_ans
    [[ "$restore_ans" =~ ^[Yy]$ ]] && RESTORE_BACKUP=true
fi

# ─── Stop waybar ─────────────────────────────────────────
header "⏸  Stopping waybar..."
pgrep -x waybar &>/dev/null && pkill waybar 2>/dev/null && success "waybar stopped" || true

# ─── Restore backup OR patch to remove ───────────────────
if $RESTORE_BACKUP; then
    header "♻️  Restoring backup..."

    LAST_TS=$(cat "$BACKUP_DIR/last_install.txt" 2>/dev/null || echo "")

    for f in config.jsonc config style.css; do
        bak=$(ls "$BACKUP_DIR/${f}.${LAST_TS}.bak" 2>/dev/null | head -1 || \
              ls "$BACKUP_DIR/${f}."*.bak 2>/dev/null | sort | tail -1 || echo "")
        if [ -n "$bak" ] && [ -f "$bak" ]; then
            cp "$bak" "$WAYBAR_DIR/$f"
            success "Restored: $f"
        fi
    done
else
    header "✂️  Removing module from config..."

    python3 "$APP_DIR/scripts/patch_waybar.py" remove 2>/dev/null || \
        warn "patch_waybar.py not found — remove the module manually"
fi

# ─── Remove installed files ───────────────────────────────
header "🗑️  Removing installed files..."

for f in "$WAYBAR_DIR/praybar.py" "$WAYBAR_DIR/assets/praybar-style.css"; do
    if [ -f "$f" ]; then
        rm "$f"
        success "Removed: $f"
    fi
done

# Ask about azan.mp3
AZAN="$WAYBAR_DIR/azan.mp3"
if [ -f "$AZAN" ]; then
    echo ""
    read -rp "  Remove azan.mp3 too? [y/N] " azan_ans
    [[ "$azan_ans" =~ ^[Yy]$ ]] && rm "$AZAN" && success "Removed: azan.mp3"
fi

# Clean up notification flags, locks, cache, and any leftover azan process
rm -f /tmp/.praybar_notified_* 2>/dev/null || true
rm -f /tmp/.azan_player_pid /tmp/.praybar_dismiss_*.sh 2>/dev/null || true
success "Cleared notification flags"

CACHE="$HOME/.cache/praybar_times_cache.json"
[ -f "$CACHE" ] && rm "$CACHE" && success "Cleared praybar times cache"

LOC_CACHE="$HOME/.cache/praybar_location_cache.json"
[ -f "$LOC_CACHE" ] && rm "$LOC_CACHE" && success "Cleared location cache"

# ─── Remove daily refresh timer ──────────────────────────
if command -v systemctl &>/dev/null; then
    systemctl --user disable --now praybar-refresh.timer 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/praybar-refresh.service" \
          "$HOME/.config/systemd/user/praybar-refresh.timer"
    systemctl --user daemon-reload 2>/dev/null || true
    success "Removed daily refresh timer"
fi

# Ask about backup folder
if [ -d "$BACKUP_DIR" ]; then
    echo ""
    read -rp "  Remove backup folder too? [y/N] " bak_ans
    if [[ "$bak_ans" =~ ^[Yy]$ ]]; then
        rm -rf "$BACKUP_DIR"
        success "Removed: $BACKUP_DIR"
    fi
fi

# ─── Restart waybar ──────────────────────────────────────
header "🔄 Restarting waybar..."
nohup waybar &>/dev/null &
disown
success "waybar restarted"

# ─── Summary ─────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}════════════════════════════════════════${RESET}"
echo -e "${BOLD}${GREEN}  ✅ Uninstall complete!${RESET}"
echo -e "${BOLD}${GREEN}════════════════════════════════════════${RESET}"
echo ""
echo -e "  waybar has been restored to its original state."
echo ""
