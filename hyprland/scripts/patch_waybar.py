#!/usr/bin/env python3
"""
patch_waybar.py — Waybar config patcher
Adds or removes the custom/praybar module from waybar config.
Supports jsonc format (// and /* */ comments are preserved).

Placement logic:
  - Inserts "custom/praybar" immediately BEFORE "clock" in whichever
    modules list "clock" lives in, so the bar reads:
      ... | 🕌 Fajr 2:41 — Thursday 01:30 | ...
  - Falls back to prepending to modules-right if clock is not found.
"""

import re
import sys
import os

MODULE_DEF = '''"custom/praybar": {
    "exec": "python3 ~/.config/waybar/praybar.py",
    "return-type": "json",
    "interval": 30,
    "tooltip": true
  }'''

HERE     = os.path.dirname(os.path.abspath(__file__))
CSS_FILE = os.path.join(HERE, '..', 'assets/praybar-style.css')


def find_config():
    for p in [
        os.path.expanduser("~/.config/waybar/config.jsonc"),
        os.path.expanduser("~/.config/waybar/config"),
        os.path.expanduser("~/.config/omarchy/waybar/config.jsonc"),
        os.path.expanduser("~/.config/omarchy/waybar/config"),
    ]:
        if os.path.exists(p):
            return p
    return None


def find_style():
    for p in [
        os.path.expanduser("~/.config/waybar/style.css"),
        os.path.expanduser("~/.config/omarchy/waybar/style.css"),
    ]:
        if os.path.exists(p):
            return p
    return None


def add_to_modules_list(raw):
    """
    Insert custom/praybar directly before 'clock' in the modules list.
    Falls back to prepending to modules-right / modules-center / modules-left.
    """
    # Try to place right before "clock"
    pattern = r'("modules-(?:left|center|right)"\s*:\s*\[)([^\]]*?)(\])'
    for m in re.finditer(pattern, raw, re.DOTALL):
        inside = m.group(2)
        if '"clock"' in inside and 'custom/praybar' not in inside:
            new_inside = inside.replace('"clock"', '"custom/praybar", "clock"', 1)
            raw = raw[:m.start(2)] + new_inside + raw[m.end(2):]
            return raw, "before clock"

    # Fallback: prepend to first available modules list
    for section in ['"modules-right"', '"modules-center"', '"modules-left"']:
        m = re.search(
            rf'({re.escape(section)}\s*:\s*\[)([^\]]*?)(\])', raw, re.DOTALL
        )
        if m:
            inside = m.group(2)
            if 'custom/praybar' not in inside:
                new_inside = '"custom/praybar", ' + inside.lstrip()
                raw = raw[:m.start(2)] + new_inside + raw[m.end(2):]
            return raw, section.strip('"')

    return raw, None


def add_module_definition(raw):
    """Insert the module definition block before the final top-level closing brace."""
    if re.search(r'"custom/praybar"\s*:', raw):
        return raw  # Already present

    depth = 0
    insert_pos = -1
    for i in range(len(raw) - 1, -1, -1):
        if raw[i] == '}':
            depth += 1
            if depth == 1:
                insert_pos = i
                break
        elif raw[i] == '{':
            depth -= 1

    if insert_pos == -1:
        return raw

    before = raw[:insert_pos].rstrip()
    if before and before[-1] not in (',', '{'):
        before += ','

    return before + f'\n\n  {MODULE_DEF}\n' + raw[insert_pos:]


def remove_from_modules_list(raw):
    """Remove custom/praybar from all modules lists."""
    raw = re.sub(r'"custom/praybar"\s*,\s*', '', raw)
    raw = re.sub(r',\s*"custom/praybar"', '', raw)
    raw = re.sub(r',\s*,', ',', raw)
    return raw


def remove_module_definition(raw):
    """Remove the custom/praybar definition block."""
    raw = re.sub(
        r',?\s*"custom/praybar"\s*:\s*\{[^{}]*\}',
        '', raw, flags=re.DOTALL
    )
    return raw


def apply(action="add"):
    config_path = find_config()
    style_path  = find_style()
    results     = []

    if not config_path:
        return False, ["ERROR: Could not find waybar config — check your config path"]

    with open(config_path, 'r') as f:
        raw = f.read()

    if action == "add":
        raw, placement = add_to_modules_list(raw)
        raw = add_module_definition(raw)

        with open(config_path, 'w') as f:
            f.write(raw)

        results.append(f"OK: custom/praybar placed {placement or 'in modules'}")
        results.append(f"OK: config saved: {config_path}")

        # Sync config -> config.jsonc if both exist
        jsonc = config_path.replace('/config', '/config.jsonc') if not config_path.endswith('.jsonc') else None
        alt   = config_path.replace('/config.jsonc', '/config') if config_path.endswith('.jsonc') else None
        for twin in [jsonc, alt]:
            if twin and os.path.exists(twin) and twin != config_path:
                import shutil
                shutil.copy2(config_path, twin)
                results.append(f"OK: synced to: {twin}")

        # Append CSS
        if style_path and os.path.exists(CSS_FILE):
            with open(style_path, 'r') as f:
                css = f.read()
            marker = '/* === Prayer Times === */'
            if marker not in css:
                snippet = open(CSS_FILE).read()
                with open(style_path, 'a') as f:
                    f.write(f'\n\n{marker}\n{snippet}')
                results.append(f"OK: CSS appended to: {style_path}")
            else:
                results.append("WARNING: Prayer CSS already present in style.css")
        elif not style_path:
            results.append("WARNING: style.css not found — add CSS manually")

    elif action == "remove":
        raw = remove_from_modules_list(raw)
        raw = remove_module_definition(raw)
        with open(config_path, 'w') as f:
            f.write(raw)
        results.append("OK: custom/praybar removed from config")

        # Sync removal to twin file
        jsonc = config_path.replace('/config', '/config.jsonc') if not config_path.endswith('.jsonc') else None
        alt   = config_path.replace('/config.jsonc', '/config') if config_path.endswith('.jsonc') else None
        for twin in [jsonc, alt]:
            if twin and os.path.exists(twin) and twin != config_path:
                import shutil
                shutil.copy2(config_path, twin)
                results.append(f"OK: synced removal to: {twin}")

        if style_path:
            with open(style_path, 'r') as f:
                css = f.read()
            marker = '/* === Prayer Times === */'
            if marker in css:
                css = re.sub(
                    rf'\n*{re.escape(marker)}.*',
                    '', css, flags=re.DOTALL
                )
                with open(style_path, 'w') as f:
                    f.write(css)
                results.append("OK: Prayer CSS removed from style.css")

    return True, results


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "add"
    ok, msgs = apply(action)
    for m in msgs:
        print(m)
    sys.exit(0 if ok else 1)
