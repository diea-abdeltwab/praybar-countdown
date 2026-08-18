#!/usr/bin/env python3
"""
patch_shell_json.py — Omarchy 4 (Quattro) shell.json patcher
Adds or removes the praybar "command" bar module from
~/.config/omarchy/shell.json.

Why this exists
----------------
Omarchy 4 replaced Waybar's config.jsonc with a single ~/.config/omarchy/shell.json
that has NO deep-merge with the shell's built-in defaults once it exists
(see docs/omarchy-shell.md: "Once the user customizes, shell.json is
canonical"). That means we can't just append our module and call it a
day the first time — if the user has never touched shell.json, we have
to first seed it from Omarchy's own shipped defaults, or we'd silently
delete every other default bar widget (clock, audio, menu, ...) the
moment we write a partial file.

Placement logic
----------------
  - Inserts the "praybar" module immediately BEFORE the clock widget
    (id starts with "omarchy.clock") in whichever bar.layout.<section>
    list it lives in, so the bar reads:
      ... | 🕌 Fajr 2:41 --  |  13:05 | ...
  - Falls back to prepending to bar.layout.center (creating it if
    needed) if no clock widget is found.

This is plain JSON (unlike Waybar's jsonc), so we parse and rewrite it
with the json module instead of regex-patching text — much less
fragile for a nested structure like this one.
"""

import json
import os
import shutil
import sys

MODULE_ID = "praybar"

MODULE_DEF = {
    "id": MODULE_ID,
    "type": "command",
    "exec": "python3 ~/.config/omarchy/bar/scripts/praybar.py",
    "interval": 30,
}


def find_user_shell_json():
    return os.path.expanduser("~/.config/omarchy/shell.json")


def find_default_shell_json():
    """
    Locate Omarchy's own shipped shell.json, used to seed a fresh
    ~/.config/omarchy/shell.json if the user doesn't have one yet.
    Tries $OMARCHY_PATH first (the documented, authoritative source —
    see AGENTS.md), then falls back to common install locations.
    """
    candidates = []

    omarchy_path = os.environ.get("OMARCHY_PATH")
    if omarchy_path:
        candidates.append(os.path.join(omarchy_path, "config/omarchy/shell.json"))

    candidates += [
        os.path.expanduser("~/.local/share/omarchy/config/omarchy/shell.json"),
        "/usr/share/omarchy/config/omarchy/shell.json",
        "/usr/lib/omarchy/config/omarchy/shell.json",
    ]

    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def load_or_seed_shell_json():
    """
    Return (data, existed_already). If the user has no shell.json yet,
    seed it from Omarchy's shipped defaults so the write below doesn't
    wipe out the rest of the bar. Returns (None, False) if neither the
    user file nor a default could be found at all.
    """
    user_path = find_user_shell_json()

    if os.path.exists(user_path):
        with open(user_path) as f:
            return json.load(f), True

    default_path = find_default_shell_json()
    if default_path:
        with open(default_path) as f:
            return json.load(f), False

    return None, False


def find_clock_location(bar_layout: dict):
    """Return (section_name, index) of the first widget id starting
    with 'omarchy.clock' inside bar.layout, or (None, None)."""
    for section in ("left", "center", "right"):
        widgets = bar_layout.get(section) or []
        for i, w in enumerate(widgets):
            if isinstance(w, dict) and str(w.get("id", "")).startswith("omarchy.clock"):
                return section, i
    return None, None


def module_present(bar_layout: dict) -> bool:
    for section in ("left", "center", "right"):
        for w in bar_layout.get(section) or []:
            if isinstance(w, dict) and w.get("id") == MODULE_ID:
                return True
    return False


def add(data: dict):
    data.setdefault("bar", {})
    bar = data["bar"]
    bar.setdefault("layout", {})
    layout = bar["layout"]

    if module_present(layout):
        return "WARNING: praybar module already present in shell.json"

    section, idx = find_clock_location(layout)
    if section is not None:
        layout[section].insert(idx, dict(MODULE_DEF))
        return f"OK: praybar placed before clock in bar.layout.{section}"

    layout.setdefault("center", [])
    layout["center"].insert(0, dict(MODULE_DEF))
    return "OK: praybar placed at the start of bar.layout.center (no clock widget found)"


def remove(data: dict):
    layout = (data.get("bar") or {}).get("layout") or {}
    removed = False
    for section in ("left", "center", "right"):
        widgets = layout.get(section)
        if not widgets:
            continue
        new_widgets = [w for w in widgets if not (isinstance(w, dict) and w.get("id") == MODULE_ID)]
        if len(new_widgets) != len(widgets):
            layout[section] = new_widgets
            removed = True
    return "OK: praybar removed from shell.json" if removed else "WARNING: praybar module was not present"


def apply(action="add"):
    user_path = find_user_shell_json()
    data, existed = load_or_seed_shell_json()
    results = []

    if data is None:
        return False, [
            "ERROR: could not find ~/.config/omarchy/shell.json or a shipped default to seed it from.",
            "        Open the Omarchy bar settings once (or set $OMARCHY_PATH) and re-run this script.",
        ]

    if action == "add":
        results.append(add(data))
    elif action == "remove":
        results.append(remove(data))
    else:
        return False, [f"ERROR: unknown action '{action}'"]

    os.makedirs(os.path.dirname(user_path), exist_ok=True)
    with open(user_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    if not existed and action == "add":
        results.append(f"OK: seeded {user_path} from Omarchy defaults before patching")
    results.append(f"OK: shell.json saved: {user_path}")
    return True, results


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "add"
    ok, msgs = apply(action)
    for m in msgs:
        print(m)
    sys.exit(0 if ok else 1)
