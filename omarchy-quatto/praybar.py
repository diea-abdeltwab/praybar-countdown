#!/usr/bin/env python3
"""
praybar — Prayer Times for the Omarchy 4 (Quattro) Quickshell bar
Fetches prayer times from the Aladhan API and displays a countdown timer.
Location is auto-detected from the device's IP address, so it works
anywhere in the world without editing this file.

This is the Omarchy 4 / Quickshell port. Omarchy 4 ("Quattro") replaced
Waybar with a single Quickshell process (omarchy-shell) that reads its
bar layout from ~/.config/omarchy/shell.json instead of Waybar's
config.jsonc. That shell still supports "command" bar modules that
poll a script on an interval and accept the exact same
{ "text", "tooltip", "class" } JSON shape Waybar used — see
docs/omarchy-shell.md ("Custom bar modules") in the Omarchy repo — so
this script's stdout contract is unchanged from the Waybar version.
Everything below this docstring (location detection, prayer-time
fetching/caching, azan playback, notifications) is identical logic to
the Waybar module; only paths and the install/patch machinery differ.
"""

import json
import time
import urllib.request
from datetime import datetime, timedelta
import os
import re
import shutil
import subprocess
import signal
import fcntl

# Leave these as None to auto-detect location from the device's IP.
# Set both to fixed numbers if you'd rather pin a specific location
# (e.g. MANUAL_LATITUDE = 29.3084, MANUAL_LONGITUDE = 30.8428).
MANUAL_LATITUDE  = None
MANUAL_LONGITUDE = None
MANUAL_CITY      = None   # optional label shown in the tooltip

# Used only if auto-detection fails AND no manual override is set.
FALLBACK_LATITUDE  = 29.3084
FALLBACK_LONGITUDE = 30.8428
FALLBACK_CITY       = "Faiyum, EG"

METHOD               = 5   # Egyptian General Authority of Survey

# "24h" → 13:05   |   "12h" → 1:05 PM
# Set automatically by install.sh based on what you choose during setup;
# change it here any time and it takes effect on the next refresh.
TIME_FORMAT          = "24h"

CACHE_FILE           = os.path.expanduser("~/.cache/praybar_times_cache.json")
LOCATION_CACHE_FILE  = os.path.expanduser("~/.cache/praybar_location_cache.json")
LOCATION_CACHE_TTL   = 24 * 3600   # re-check IP location once a day

# IP geolocation is only accurate to a few km, and can wobble slightly
# between checks (or between the two providers) even though you haven't
# actually moved. If a fresh lookup lands within this many degrees of the
# last known location (~5-6 km at Egypt's latitude), we keep the OLD
# coordinates instead of the new ones. This is what actually stops the
# prayer times from drifting by a minute or two every day: the timings
# cache is keyed on rounded lat/lon, so any tiny jitter here was forcing
# a brand-new Aladhan fetch with slightly different coordinates.
LOCATION_JITTER_TOLERANCE_DEG = 0.05

# Omarchy 4 has no waybar directory — "one-off" custom bar command
# modules live under ~/.config/omarchy/bar/scripts/ by convention
# (see docs/omarchy-shell.md, "Custom bar modules"). azan.mp3 is
# installed next to this script, same as it sat next to praybar.py
# in ~/.config/waybar/ on the Waybar version.
INSTALL_DIR          = os.path.expanduser("~/.config/omarchy/bar/scripts")
AZAN_PID_FILE        = "/tmp/.azan_player_pid"

PRAYER_NAMES = {
    "Fajr":    "Fajr",
    "Sunrise": "Sunrise",
    "Dhuhr":   "Dhuhr",
    "Asr":     "Asr",
    "Maghrib": "Maghrib",
    "Isha":    "Isha",
}

# A distinct glyph per prayer so the bar segment is recognizable at a
# glance without reading the label — and so the tooltip's daily list
# reads less like a plain table. Plain Unicode emoji rather than Nerd
# Font glyphs on purpose: those render everywhere, Nerd Font codepoints
# don't (and Quattro no longer guarantees Waybar's icon-font setup).
PRAYER_ICONS = {
    "Fajr":    "🌙",
    "Sunrise": "🌅",
    "Dhuhr":   "☀️",
    "Asr":     "🌤️",
    "Maghrib": "🌇",
    "Isha":    "🌌",
}

# Shown instead of the prayer's own icon inside the urgency window —
# a single unmistakable visual cue that doesn't depend on the shell
# giving any particular meaning to the JSON "class" field (see
# omarchy4/README.md, "Design notes").
BELL_ICON = "🔔"

# Countdown starts changing color at this many seconds remaining (15 min),
# and the icon escalates to BELL_ICON inside this many seconds (5 min).
# Matches the two-stage urgency the Waybar/CSS version had.
COLOR_THRESHOLD_SECS = 15 * 60
BELL_THRESHOLD_SECS  = 5 * 60

# Fallback color used if the active Omarchy theme's colors.toml can't be
# found or doesn't define anything red-ish — a muted red that reads
# clearly against the dark background every stock Omarchy theme ships.
FALLBACK_URGENT_COLOR = "#e06c75"

# Where Quattro keeps the *active* theme's rendered colors.toml. This
# moved between Omarchy versions (see PR #6231: "generated theme state
# moves from ~/.config/omarchy/current to ~/.local/state/omarchy/current"
# in Quattro), so we check the new location first and fall back to the
# old one in case a given install still resolves it there.
THEME_COLORS_PATHS = [
    os.path.expanduser("~/.local/state/omarchy/current/theme/colors.toml"),
    os.path.expanduser("~/.config/omarchy/current/theme/colors.toml"),
]

PRAYER_KEYS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]


# ─── Location detection ───────────────────────────────────────────────────────
#
# Phones and browsers ("how does Google know where I am?") get their
# accuracy mainly from scanning nearby Wi-Fi access points and matching
# them against a crowd-sourced Wi-Fi positioning database — GPS/IP are
# only used when Wi-Fi isn't available. This is why Google Maps on a
# laptop with no GPS chip can still place you on the right street, while
# plain IP geolocation only knows which city your ISP is registered in
# (often the ISP's regional hub, e.g. Cairo for a Fayoum connection).
## We do the same thing here: scan nearby APs (via NetworkManager, `iw`,
# or `iwlist` — whichever is available) and query Mozilla's public, free
# Wi-Fi positioning service (the same database Firefox uses for HTML5
# geolocation). If that succeeds we get street/neighbourhood-level
# accuracy. If no Wi-Fi adapter, no nearby APs, or the service is
# unreachable, we transparently fall back to the old IP-based lookup —
# nothing breaks on machines without Wi-Fi.

def _scan_wifi_aps():
    """
    Return nearby Wi-Fi APs as Mozilla-format dicts, or None if no
    scanning tool is available / no APs are found. Tries several tools
    in order since not every system has NetworkManager — minimal
    Sway/Hyprland/i3 setups often only have `iw` or `iwlist` instead.
    """
    for scanner in (_scan_via_nmcli, _scan_via_iw, _scan_via_iwlist):
        aps = scanner()
        if aps:
            return aps
    return None


def _scan_via_nmcli():
    if not shutil.which("nmcli"):
        return None
    try:
        subprocess.run(
            ["nmcli", "device", "wifi", "rescan"],
            timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass
    try:
        out = subprocess.run(
            ["nmcli", "-f", "BSSID,SIGNAL", "dev", "wifi", "list"],
            timeout=10, capture_output=True, text=True, check=True,
        ).stdout
    except Exception:
        return None

    aps = []
    for mac, signal_pct in re.findall(
        r"([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\s+(\d{1,3})", out
    ):
        # nmcli reports signal as 0-100%; Mozilla's API wants dBm.
        dbm = int(int(signal_pct) / 2 - 100)
        aps.append({"macAddress": mac, "signalStrength": dbm})
    return aps or None


def _find_wifi_interface():
    """Return the first wireless interface name (e.g. 'wlan0'), or None."""
    try:
        out = subprocess.run(
            ["iw", "dev"], timeout=5, capture_output=True, text=True, check=True,
        ).stdout
        m = re.search(r"Interface\s+(\S+)", out)
        return m.group(1) if m else None
    except Exception:
        return None


def _scan_via_iw():
    """
    Use `iw` directly (present on most Linux systems via iw/wireless-tools,
    even without NetworkManager). Tries an active scan first; if that's
    blocked by permissions, falls back to the interface's last cached
    scan results (`scan dump`), which doesn't require elevated rights.
    """
    if not shutil.which("iw"):
        return None
    iface = _find_wifi_interface()
    if not iface:
        return None

    out = None
    try:
        out = subprocess.run(
            ["iw", "dev", iface, "scan"],
            timeout=15, capture_output=True, text=True,
        ).stdout
    except Exception:
        out = None

    if not out or "BSS " not in out:
        try:
            out = subprocess.run(
                ["iw", "dev", iface, "scan", "dump"],
                timeout=10, capture_output=True, text=True,
            ).stdout
        except Exception:
            return None

    if not out:
        return None

    aps = []
    current_mac = None
    for line in out.splitlines():
        line = line.strip()
        m = re.match(r"BSS ([0-9A-Fa-f:]{17})", line)
        if m:
            current_mac = m.group(1)
            continue
        if current_mac and line.startswith("signal:"):
            m2 = re.search(r"(-?\d+(?:\.\d+)?)\s*dBm", line)
            if m2:
                aps.append({
                    "macAddress": current_mac,
                    "signalStrength": int(float(m2.group(1))),
                })
            current_mac = None
    return aps or None


def _scan_via_iwlist():
    """Older wireless-tools fallback, used if `iw` isn't available either."""
    if not shutil.which("iwlist"):
        return None
    iface = _find_wifi_interface() or "wlan0"
    try:
        out = subprocess.run(
            ["iwlist", iface, "scanning"],
            timeout=15, capture_output=True, text=True,
        ).stdout
    except Exception:
        return None

    aps = []
    current_mac = None
    for line in out.splitlines():
        line = line.strip()
        m = re.search(r"Address:\s*([0-9A-Fa-f:]{17})", line)
        if m:
            current_mac = m.group(1)
            continue
        if current_mac and "Signal level" in line:
            m2 = re.search(r"Signal level[=:]\s*(-?\d+)\s*dBm", line)
            if m2:
                aps.append({
                    "macAddress": current_mac,
                    "signalStrength": int(m2.group(1)),
                })
            current_mac = None
    return aps or None


def _wifi_geolocate():
    """
    Estimate (lat, lon) from nearby Wi-Fi APs via Mozilla Location Service.
    Returns None if there aren't enough APs for a confident fix, or the
    request fails for any reason (offline, rate-limited, no matches, etc.)
    """
    aps = _scan_wifi_aps()
    if not aps or len(aps) < 2:
        return None

    try:
        req = urllib.request.Request(
            "https://location.services.mozilla.com/v1/geolocate?key=test",
            data=json.dumps({"wifiAccessPoints": aps}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        accuracy_m = data.get("accuracy", 999999)
        if accuracy_m > 50000:   # sanity check — reject a wildly loose fix
            return None
        return float(data["location"]["lat"]), float(data["location"]["lng"])
    except Exception:
        return None


def _reverse_geocode(lat, lon):
    """Best-effort 'City, CC' label for a coordinate, via OpenStreetMap."""
    try:
        url = (
            f"https://nominatim.openstreetmap.org/reverse"
            f"?format=json&lat={lat}&lon={lon}&zoom=10&accept-language=en"
        )
        req = urllib.request.Request(url, headers={
            "User-Agent": "praybar/1.0 (personal prayer-times waybar widget)",
            "Accept":     "application/json",
        })
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read())
        addr = data.get("address", {})
        city = (
            addr.get("city") or addr.get("town")
            or addr.get("village") or addr.get("county") or ""
        )
        country = addr.get("country_code", "").upper()
        label = f"{city}, {country}".strip(", ")
        return label or None
    except Exception:
        return None


def _wttr_geolocate():
    """
    Query wttr.in's own IP-based geolocation — the exact same backend
    Omarchy's built-in weather widget uses under the hood (IP2Location,
    with MaxMind as a fallback). Real-world testing shows this resolves
    many ISPs (Egyptian ones included) far more accurately than the
    generic ipapi.co/ip-api.com lookups below, which tend to collapse to
    the ISP's registered regional hub city instead of your actual city.
    """
    try:
        req = urllib.request.Request(
            "https://wttr.in/?format=j1",
            headers={"User-Agent": "curl/8.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        area    = data["nearest_area"][0]
        lat     = float(area["latitude"])
        lon     = float(area["longitude"])
        city    = area["areaName"][0]["value"]
        country = area.get("country", [{}])[0].get("value", "")
        label   = f"{city}, {country}".strip(", ")
        return lat, lon, label
    except Exception:
        return None


# Confidence ranking for each detection method. A lower-confidence
# reading is never allowed to silently overwrite a higher-confidence
# one just because it disagrees — see _accept_reading() below. This is
# what stops a single flaky wttr.in request from bouncing your saved
# location to a worse IP-based guess.
TIER_CONFIDENCE = {"manual": 4, "wifi": 3, "wttr": 2, "ip": 1}


def _accept_reading(lat, lon, city, source, stale_cached):
    """
    Apply jitter tolerance + confidence checking against the last cached
    fix, persist the result, and return the coordinates to use.

    - If the new reading is basically the same spot as last time (within
      LOCATION_JITTER_TOLERANCE_DEG), keep the OLD coordinates so the
      timings cache key doesn't change and prayer times don't shift for
      no reason.
    - If it's a genuinely different location, only accept it if it came
      from a tier at least as trustworthy as whatever produced the
      cached location. A lower-confidence tier (e.g. generic IP)
      disagreeing with a higher-confidence one (e.g. wttr.in or Wi-Fi)
      almost always means THAT lookup failed or was inaccurate this one
      time — not that you actually moved — so we keep the last known
      good fix instead of overwriting it with a worse guess.
    """
    final_lat, final_lon, final_city, final_source = lat, lon, city, source

    if stale_cached:
        same_place = (
            abs(stale_cached.get("lat", 999) - lat) <= LOCATION_JITTER_TOLERANCE_DEG
            and abs(stale_cached.get("lon", 999) - lon) <= LOCATION_JITTER_TOLERANCE_DEG
        )
        old_conf = TIER_CONFIDENCE.get(stale_cached.get("source"), 0)
        new_conf = TIER_CONFIDENCE.get(source, 0)

        if same_place:
            final_lat, final_lon, final_city = (
                stale_cached["lat"], stale_cached["lon"], stale_cached["city"],
            )
            final_source = source if new_conf > old_conf else stale_cached.get("source", source)
        elif new_conf < old_conf:
            final_lat, final_lon, final_city, final_source = (
                stale_cached["lat"], stale_cached["lon"],
                stale_cached["city"], stale_cached.get("source", source),
            )
        # else: equal-or-higher confidence disagrees → genuine change, accept as-is

    # Refresh the timestamp regardless, so a rejected downgrade doesn't
    # cause every waybar tick to retry the network until a better tier
    # succeeds — we simply wait out the normal cache TTL either way.
    with open(LOCATION_CACHE_FILE, "w") as f:
        json.dump(
            {
                "lat": final_lat, "lon": final_lon, "city": final_city,
                "source": final_source, "fetched_at": time.time(),
            },
            f,
        )
    return final_lat, final_lon, final_city


def get_location():
    """
    Return (lat, lon, city_label) for prayer-time calculation.

    Order of precedence:
      1. MANUAL_LATITUDE / MANUAL_LONGITUDE, if set at the top of this file.
      2. Wi-Fi based positioning (Mozilla Location Service) — the same
         technique phones/browsers use, accurate to street level.
      3. wttr.in's IP geolocation (IP2Location/MaxMind) — the same backend
         Omarchy's weather widget uses; noticeably more accurate per-ISP
         than the generic providers below, with no setup required.
      4. Generic IP-based geolocation (ipapi.co, then ip-api.com), as a
         further fallback if wttr.in is unreachable.
      5. The last successfully detected location, if a fresh lookup fails.
      6. FALLBACK_LATITUDE / FALLBACK_LONGITUDE as a last resort.

    All auto-detected results are cached for LOCATION_CACHE_TTL seconds
    so we don't hammer any provider on every waybar refresh. If a lower
    tier (e.g. generic IP) disagrees with what a higher tier (Wi-Fi or
    wttr.in) previously found, the disagreement is treated as that
    lookup having failed this one time rather than you having moved —
    the last known good location is kept instead of being overwritten.
    """
    if MANUAL_LATITUDE is not None and MANUAL_LONGITUDE is not None:
        return MANUAL_LATITUDE, MANUAL_LONGITUDE, (MANUAL_CITY or "Manual location")

    os.makedirs(os.path.dirname(LOCATION_CACHE_FILE), exist_ok=True)

    stale_cached = None
    if os.path.exists(LOCATION_CACHE_FILE):
        try:
            with open(LOCATION_CACHE_FILE) as f:
                stale_cached = json.load(f)
            if time.time() - stale_cached.get("fetched_at", 0) < LOCATION_CACHE_TTL:
                return stale_cached["lat"], stale_cached["lon"], stale_cached["city"]
        except Exception:
            stale_cached = None

    # ── Tier 1: Wi-Fi positioning ──
    wifi_fix = _wifi_geolocate()
    if wifi_fix:
        lat, lon = wifi_fix
        city = _reverse_geocode(lat, lon) or "Detected location"
        return _accept_reading(lat, lon, city, "wifi", stale_cached)

    # ── Tier 2: wttr.in geolocation (same backend Omarchy's weather uses) ──
    wttr_fix = _wttr_geolocate()
    if wttr_fix:
        lat, lon, city = wttr_fix
        return _accept_reading(lat, lon, city, "wttr", stale_cached)

    # ── Tier 3: generic IP-based geolocation ──
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) WaybarPrayer/1.0",
        "Accept":     "application/json",
    }
    providers = [
        ("https://ipapi.co/json/", lambda d: (
            float(d["latitude"]), float(d["longitude"]),
            f'{d.get("city", "")}, {d.get("country_code", "")}'.strip(", "),
        )),
        ("http://ip-api.com/json/", lambda d: (
            float(d["lat"]), float(d["lon"]),
            f'{d.get("city", "")}, {d.get("countryCode", "")}'.strip(", "),
        )),
    ]
    for url, parse in providers:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read())
            lat, lon, city = parse(data)
            return _accept_reading(lat, lon, city, "ip", stale_cached)
        except Exception:
            continue

    # ── Tier 4: reuse last known location instead of jumping cities ──
    if os.path.exists(LOCATION_CACHE_FILE):
        try:
            with open(LOCATION_CACHE_FILE) as f:
                cached = json.load(f)
            return cached["lat"], cached["lon"], cached["city"]
        except Exception:
            pass

    return FALLBACK_LATITUDE, FALLBACK_LONGITUDE, FALLBACK_CITY


# ─── Prayer time fetching ─────────────────────────────────────────────────────

def fetch_prayer_times(lat, lon):
    today    = datetime.now().strftime("%d-%m-%Y")
    date_iso = datetime.now().strftime("%Y-%m-%d")
    loc_key  = f"{lat:.2f},{lon:.2f}"
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)

    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                cache = json.load(f)
            # Only reuse the cache if it's for TODAY *and* the same
            # location — this is what keeps times from "changing" when
            # the detected location shifts slightly between runs.
            if cache.get("date") == date_iso and cache.get("loc") == loc_key:
                return cache["timings"]
        except Exception:
            pass

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) WaybarPrayer/1.0",
        "Accept":     "application/json",
    }

    url = (
        f"https://api.aladhan.com/v1/timings/{today}"
        f"?latitude={lat}&longitude={lon}&method={METHOD}"
    )

    # Retry the SAME location a few times instead of falling back to a
    # different city (the old Cairo fallback was why times looked like
    # they changed depending on your location/network).
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())
            timings = data["data"]["timings"]
            with open(CACHE_FILE, "w") as f:
                json.dump({"date": date_iso, "loc": loc_key, "timings": timings}, f)
            return timings
        except Exception:
            continue

    # All attempts failed: fall back to the last cached timings for this
    # SAME location, rather than a different city.
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                cache = json.load(f)
            if cache.get("loc") == loc_key:
                return cache.get("timings")
        except Exception:
            pass

    return None


# ─── Next prayer logic ────────────────────────────────────────────────────────

def get_next_prayer(timings):
    now       = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    for key in PRAYER_KEYS:
        prayer_dt = datetime.strptime(
            f"{today_str} {timings[key][:5]}", "%Y-%m-%d %H:%M"
        )
        if prayer_dt > now:
            return key, prayer_dt

    tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    return "Fajr", datetime.strptime(
        f"{tomorrow_str} {timings['Fajr'][:5]}", "%Y-%m-%d %H:%M"
    )


def format_countdown(delta):
    total = max(0, int(delta.total_seconds()))
    h, rem = divmod(total, 3600)
    m      = rem // 60
    return f"{h}:{m:02d}" if h else f"{m}m"


# ─── Audio ────────────────────────────────────────────────────────────────────

def kill_azan():
    """Kill the running azan player process group."""
    if not os.path.exists(AZAN_PID_FILE):
        return
    try:
        with open(AZAN_PID_FILE) as f:
            pid = int(f.read().strip())
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            pass  # already dead — that's fine
        except Exception:
            # Fallback: kill just the pid
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
    except Exception:
        pass
    try:
        os.remove(AZAN_PID_FILE)
    except Exception:
        pass


def play_azan():
    """Start azan audio and save PID. Kills any previous instance first.

    Returns the PID of the started player (or None if nothing could be
    started), so the caller can track this exact process instead of
    relying solely on AZAN_PID_FILE, which can be overwritten if another
    invocation starts a second player before this one is dismissed.
    """
    kill_azan()

    azan_file = os.path.join(INSTALL_DIR, "azan.mp3")
    proc      = None

    if os.path.exists(azan_file):
        for player_cmd in [
            ["mpv", "--no-terminal", "--no-video", "--no-audio-display",
             "--vo=null", "--volume=100", azan_file],
            ["paplay", azan_file],
            ["aplay",  azan_file],
        ]:
            try:
                proc = subprocess.Popen(
                    player_cmd,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                break
            except FileNotFoundError:
                continue
    else:
        # Fallback: system sounds
        for sound in [
            "/usr/share/sounds/freedesktop/stereo/complete.oga",
            "/usr/share/sounds/alsa/Front_Center.wav",
        ]:
            if os.path.exists(sound):
                try:
                    proc = subprocess.Popen(
                        ["paplay", sound],
                        start_new_session=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    break
                except Exception:
                    pass

    if proc:
        try:
            with open(AZAN_PID_FILE, "w") as f:
                f.write(str(proc.pid))
        except Exception:
            pass
        return proc.pid
    return None


# ─── Notification ─────────────────────────────────────────────────────────────

def _build_dismiss_script(prayer_name: str, azan_pid) -> str:
    """
    Return a small shell script that:
      1. Shows a persistent critical notification (with Dismiss button if supported).
      2. Blocks until dismissed.
      3. Kills the azan player on exit.

    We run this as a fully detached child process so the waybar exec cycle
    can finish immediately without waiting for the user to dismiss.

    IMPORTANT: this script kills the exact PID it was launched with
    (azan_pid), not "whatever is currently in AZAN_PID_FILE". If a race
    ever lets a second azan start before this one is dismissed, the
    shared PID file could get overwritten — but each dismiss script
    still knows and kills its OWN player, so nothing is left orphaned.
    """
    pid_file = AZAN_PID_FILE
    pid_str  = str(azan_pid) if azan_pid else ""
    return f"""\
#!/bin/sh
# Auto-generated by praybar.py — safe to delete

kill_azan() {{
    pid="{pid_str}"
    if [ -n "$pid" ]; then
        kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    fi
    # Also clear the shared pointer file, but only if it still points at us
    if [ -f "{pid_file}" ] && [ "$(cat "{pid_file}" 2>/dev/null)" = "$pid" ]; then
        rm -f "{pid_file}"
    fi
}}

# Try notify-send with --wait (libnotify >= 0.8)
if notify-send --help 2>&1 | grep -q -- '--wait'; then
    notify-send \\
        --urgency=critical \\
        --wait \\
        --action="default=Dismiss" \\
        "🕌 {prayer_name}" \\
        "الله أكبر — Allahu Akbar\\nTap Dismiss to stop the azan." 2>/dev/null || true
else
    # Older libnotify: just show a timed notification, azan runs its full length
    notify-send \\
        --urgency=critical \\
        --expire-time=90000 \\
        "🕌 {prayer_name}" \\
        "الله أكبر — Allahu Akbar" 2>/dev/null || true
    # Wait for the azan player to finish naturally
    [ -n "$pid" ] && tail --pid="$pid" -f /dev/null 2>/dev/null || true
fi

kill_azan
"""


def send_notification_and_sound(prayer_name: str):
    """
    Play azan, then launch a detached shell that shows a persistent notification
    and kills the azan when the user dismisses it.
    """
    azan_pid = play_azan()

    script      = _build_dismiss_script(prayer_name, azan_pid)
    script_path = f"/tmp/.praybar_dismiss_{os.getpid()}.sh"

    try:
        with open(script_path, "w") as f:
            f.write(script)
        os.chmod(script_path, 0o755)

        # Double-fork: detach completely from the waybar exec cycle
        subprocess.Popen(
            ["sh", script_path],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except Exception:
        pass


# ─── Notification gate ────────────────────────────────────────────────────────

def check_notification(prayer_key: str, prayer_dt: datetime):
    """Fire notification+azan once per prayer, within a ±90-second window.

    Waybar can invoke this script every `interval` seconds (30s by default),
    so several instances can be alive within the same notification window.
    The old code did "if not exists(flag): create(flag); fire()" as two
    separate steps — if two instances ran close enough together (e.g. right
    after the machine wakes from sleep and waybar/cron catch up on missed
    ticks in a burst), BOTH could see the flag as missing before either
    created it, and both would fire the azan. We now guard the whole
    check-then-create sequence with an flock so it's atomic: only one
    process can ever win the race, no matter how close together they run.
    """
    secs = (prayer_dt - datetime.now()).total_seconds()
    if not (-30 <= secs <= 90):
        return

    flag = (
        f"/tmp/.praybar_notified_"
        f"{prayer_key}_{prayer_dt.strftime('%Y%m%d%H%M')}"
    )
    lock_path = flag + ".lock"

    with open(lock_path, "w") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)  # blocks until any other run finishes
        if os.path.exists(flag):
            return
        open(flag, "w").close()
        send_notification_and_sound(PRAYER_NAMES[prayer_key])


# ─── Theme color ────────────────────────────────────────────────────────────

def get_urgent_color() -> str:
    """
    Best-effort read of a red/urgent-looking hex color from the active
    Omarchy theme, so the countdown's urgency color actually matches
    the user's theme instead of a hardcoded one. Falls back to
    FALLBACK_URGENT_COLOR if colors.toml can't be found or parsed —
    this is cosmetic, so failure here must never break the module.

    colors.toml's officially documented keys are just "foreground" and
    "background" (docs/omarchy-shell.md); "urgent" isn't guaranteed to
    exist there (it may only live in the per-theme shell.toml surface
    roles instead). So this checks a few plausible key names in order
    of how likely each is to actually be a red: an explicit "urgent",
    then the conventional ANSI "red"/"color1" that Omarchy's legacy
    colorN aliases are confirmed to still carry.
    """
    candidate_keys = ("urgent", "red", "color1")

    for path in THEME_COLORS_PATHS:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r") as f:
                content = f.read()
        except OSError:
            continue

        for key in candidate_keys:
            m = re.search(
                rf'^\s*{re.escape(key)}\s*=\s*["\']?(#?[0-9a-fA-F]{{6}})["\']?\s*$',
                content,
                re.MULTILINE,
            )
            if m:
                hexval = m.group(1)
                return hexval if hexval.startswith("#") else f"#{hexval}"

    return FALLBACK_URGENT_COLOR


# ─── Time formatting ───────────────────────────────────────────────────────────

def format_time(hhmm: str) -> str:
    """Format an 'HH:MM' (24h) string from the API per TIME_FORMAT."""
    dt = datetime.strptime(hhmm[:5], "%H:%M")
    if TIME_FORMAT == "12h":
        # %-I isn't portable everywhere (e.g. some minimal builds), so
        # strip a leading zero manually instead of relying on %-I.
        return dt.strftime("%I:%M %p").lstrip("0")
    return dt.strftime("%H:%M")


# ─── Tooltip ─────────────────────────────────────────────────────────────────

def build_tooltip(timings: dict, next_key: str, city: str) -> str:
    lines = [f"🕌  Prayer Times — {city}", ""]
    for key in ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]:
        marker = " ←" if key == next_key else ""
        icon   = PRAYER_ICONS[key]
        lines.append(f"{icon}  {PRAYER_NAMES[key]:<8} {format_time(timings[key])}{marker}")
    return "\n".join(lines)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    lat, lon, city = get_location()
    timings = fetch_prayer_times(lat, lon)

    if not timings:
        print(json.dumps({
            "text":    "🌐  –  --",
            "tooltip": "Could not fetch prayer times.\nCheck your internet connection.",
        }))
        return

    prayer_key, prayer_dt = get_next_prayer(timings)
    now       = datetime.now()
    countdown = format_countdown(prayer_dt - now)

    check_notification(prayer_key, prayer_dt)

    tooltip = build_tooltip(timings, prayer_key, city)
    secs    = (prayer_dt - now).total_seconds()
    warning = secs < COLOR_THRESHOLD_SECS   # < 15 min: countdown changes color
    urgent  = secs < BELL_THRESHOLD_SECS    # < 5 min:  icon escalates to a bell

    icon = BELL_ICON if urgent else PRAYER_ICONS[prayer_key]

    countdown_display = countdown
    if warning:
        # <font color="..."> rather than the JSON "class" field: Qt/QML's
        # Text element auto-detects and renders this kind of inline markup
        # (Text.StyledText) regardless of whether the shell gives "class"
        # any meaning for a plain command module — see omarchy4/README.md,
        # "Design notes", for why "class" alone wasn't reliable here.
        countdown_display = f'<font color="{get_urgent_color()}">{countdown}</font>'

    # Trailing "--" is a plain visual separator from the next bar module
    # (e.g. the clock) — Quattro's bar has no automatic module divider.
    text = f"{icon}  {PRAYER_NAMES[prayer_key]}  {countdown_display}  --"

    result = {"text": text, "tooltip": tooltip}
    # "urgent" is the one class name actually documented to mean
    # something to the shell (Color.urgent, the same token battery/
    # network warnings use) — see docs/omarchy-shell.md. Sent as a
    # bonus alongside the guaranteed <font> coloring above, not instead
    # of it.
    if warning:
        result["class"] = "urgent"

    print(json.dumps(result))


if __name__ == "__main__":
    main()
