#!/usr/bin/env bash
# ============================================================
#  uninstall.sh — praybar (Omarchy 4 "Quattro" / Quickshell)
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

OMARCHY_CFG="$HOME/.config/omarchy"
BAR_SCRIPTS_DIR="$OMARCHY_CFG/bar/scripts"
SHELL_JSON="$OMARCHY_CFG/shell.json"
BACKUP_DIR="$OMARCHY_CFG/.praybar-backup"

# ─── Confirm ─────────────────────────────────────────────
echo -e "${BOLD}${RED}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║   🗑️  Uninstall praybar (Omarchy 4)   ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${RESET}"
echo "  This will:"
echo "  • Remove praybar.py from the bar scripts dir"
echo "  • Remove the \"praybar\" module entry from shell.json"
echo "  • Optionally restore your pre-install shell.json backup"
echo ""
read -rp "  Are you sure? [y/N] " ans
[[ "$ans" =~ ^[Yy]$ ]] || { info "Aborted — nothing was changed."; exit 0; }

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── Offer backup restore ────────────────────────────────
RESTORE_BACKUP=false
if [ -d "$BACKUP_DIR" ] && ls "$BACKUP_DIR"/shell.json.*.bak &>/dev/null 2>&1; then
    echo ""
    warn "Found a backup of shell.json from before the install:"
    ls -lh "$BACKUP_DIR"/shell.json.*.bak 2>/dev/null | awk '{print "   " $NF " (" $5 ")"}'
    echo ""
    read -rp "  Restore that backup instead of patching? [y/N] " restore_ans
    [[ "$restore_ans" =~ ^[Yy]$ ]] && RESTORE_BACKUP=true
fi

# ─── Restore backup OR patch to remove ───────────────────
if $RESTORE_BACKUP; then
    header "♻️  Restoring backup..."

    LAST_TS=$(cat "$BACKUP_DIR/last_install.txt" 2>/dev/null || echo "")
    bak="$BACKUP_DIR/shell.json.${LAST_TS}.bak"
    [ -f "$bak" ] || bak=$(ls "$BACKUP_DIR"/shell.json.*.bak 2>/dev/null | sort | tail -1 || echo "")

    if [ -n "$bak" ] && [ -f "$bak" ]; then
        cp "$bak" "$SHELL_JSON"
        success "Restored: shell.json"
    else
        warn "No backup file found — falling back to patch-based removal"
        RESTORE_BACKUP=false
    fi
fi

if ! $RESTORE_BACKUP; then
    header "✂️  Removing module from shell.json..."
    python3 "$APP_DIR/scripts/patch_shell_json.py" remove 2>/dev/null || \
        warn "patch_shell_json.py not found or shell.json missing — remove the module manually"
fi

# ─── Remove installed files ───────────────────────────────
header "🗑️  Removing installed files..."

if [ -f "$BAR_SCRIPTS_DIR/praybar.py" ]; then
    rm "$BAR_SCRIPTS_DIR/praybar.py"
    success "Removed: praybar.py"
fi

# Ask about azan.mp3
AZAN="$BAR_SCRIPTS_DIR/azan.mp3"
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

# ─── Reload the Omarchy shell ────────────────────────────
header "🔄 Reloading the Omarchy shell..."

if command -v omarchy-shell &>/dev/null && omarchy-shell shell reloadConfig &>/dev/null; then
    success "Sent reloadConfig to the running shell"
elif command -v omarchy-restart-shell &>/dev/null; then
    omarchy-restart-shell &>/dev/null || true
    success "Restarted the Omarchy shell"
else
    warn "Could not reload automatically — log out/in to fully clear the module"
fi

# ─── Summary ─────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}════════════════════════════════════════${RESET}"
echo -e "${BOLD}${GREEN}  ✅ Uninstall complete!${RESET}"
echo -e "${BOLD}${GREEN}════════════════════════════════════════${RESET}"
echo ""
echo -e "  The Omarchy bar has been restored to its original state."
echo ""
