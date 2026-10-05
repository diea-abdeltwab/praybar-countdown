#!/usr/bin/env python3
"""
praybar — Prayer Times for Waybar
Fetches prayer times from Aladhan API and displays a countdown timer.
Location is auto-detected from the device's IP address, so it works
anywhere in the world without editing this file.
"""

import json
import urllib.request
from datetime import datetime, timedelta
import os
import subprocess
import signal
import fcntl

# Location is always detected automatically (there is no manual override and
# no built-in default city). It is re-detected once per calendar day: the daily
# refresh timer fires at 00:00 and looks it up again together with that day's
# prayer times, so moving to another city needs no configuration.

METHOD               = 5   # Egyptian General Authority of Survey

# "24h" → 13:05   |   "12h" → 1:05 PM
# Set automatically by install.sh based on what you choose during setup;
# change it here any time and it takes effect on the next refresh.
TIME_FORMAT          = "24h"

CACHE_FILE           = os.path.expanduser("~/.cache/praybar_times_cache.json")
LOCATION_CACHE_FILE  = os.path.expanduser("~/.cache/praybar_location_cache.json")

# IP geolocation is only accurate to a few km, and can wobble slightly
# between checks (or between the two providers) even though you haven't
# actually moved. If a fresh lookup lands within this many degrees of the
# last known location (~5-6 km at Egypt's latitude), we keep the OLD
# coordinates instead of the new ones. This is what actually stops the
# prayer times from drifting by a minute or two every day: the timings
# cache is keyed on rounded lat/lon, so any tiny jitter here was forcing
# a brand-new Aladhan fetch with slightly different coordinates.
LOCATION_JITTER_TOLERANCE_DEG = 0.05
INSTALL_DIR          = os.path.expanduser("~/.config/waybar")
AZAN_PID_FILE        = "/tmp/.azan_player_pid"

PRAYER_NAMES = {
    "Fajr":    "Fajr",
    "Sunrise": "Sunrise",
    "Dhuhr":   "Dhuhr",
    "Asr":     "Asr",
    "Maghrib": "Maghrib",
    "Isha":    "Isha",
}

PRAYER_KEYS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]


# ─── Location detection ───────────────────────────────────────────────────────
#
# Location comes from IP geolocation: wttr.in first (the same backend Omarchy's
# weather widget uses), then generic IP providers. An IP lookup only knows your
# ISP's registered city - often a regional hub, a big city near you rather than
# your own town - which is one more reason the location is re-checked every
# night. (A Wi-Fi positioning tier used to sit in front of these; it relied on
# Mozilla Location Service, which Mozilla retired in 2024, so it was removed.)

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
TIER_CONFIDENCE = {"wttr": 2, "ip": 1}


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
      disagreeing with a higher-confidence one (e.g. wttr.in)
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
                "source": final_source, "date": datetime.now().strftime("%Y-%m-%d"),
            },
            f,
        )
    return final_lat, final_lon, final_city


def get_location():
    """
    Return (lat, lon, city_label) for prayer-time calculation, or None if the
    location cannot be determined.

    The location is ALWAYS auto-detected, and re-detected once per calendar
    day: a cached fix is only trusted for the day it was made, so the first
    run after midnight (the daily timer fires at 00:00) looks it up again
    together with that day's prayer times.

    Order of precedence:
      1. wttr.in's IP geolocation (IP2Location/MaxMind) — the same backend
         Omarchy's weather widget uses; noticeably more accurate per-ISP
         than the generic providers below, with no setup required.
      2. Generic IP-based geolocation (ipapi.co, then ip-api.com), as a
         further fallback if wttr.in is unreachable.
      3. The last successfully detected location, if a fresh lookup fails.
      4. Otherwise None — there is deliberately no built-in default city,
         so you get a clear error instead of times for the wrong place.

    If a lower tier (e.g. generic IP) disagrees with what a higher tier
    (wttr.in) previously found, the disagreement is treated as that
    lookup having failed this one time rather than you having moved — the
    last known good location is kept instead of being overwritten.
    """
    os.makedirs(os.path.dirname(LOCATION_CACHE_FILE), exist_ok=True)

    stale_cached = None
    if os.path.exists(LOCATION_CACHE_FILE):
        try:
            with open(LOCATION_CACHE_FILE) as f:
                stale_cached = json.load(f)
            if stale_cached.get("date") == datetime.now().strftime("%Y-%m-%d"):
                return stale_cached["lat"], stale_cached["lon"], stale_cached["city"]
        except Exception:
            stale_cached = None

    # ── Tier 1: wttr.in geolocation (same backend Omarchy's weather uses) ──
    wttr_fix = _wttr_geolocate()
    if wttr_fix:
        lat, lon, city = wttr_fix
        return _accept_reading(lat, lon, city, "wttr", stale_cached)

    # ── Tier 2: generic IP-based geolocation ──
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

    # ── Tier 3: reuse last known location instead of jumping cities ──
    if os.path.exists(LOCATION_CACHE_FILE):
        try:
            with open(LOCATION_CACHE_FILE) as f:
                cached = json.load(f)
            return cached["lat"], cached["lon"], cached["city"]
        except Exception:
            pass

    return None


# ─── Prayer time fetching ─────────────────────────────────────────────────────

def fetch_prayer_times(lat, lon):
    today    = datetime.now().strftime("%d-%m-%Y")
    date_iso = datetime.now().strftime("%Y-%m-%d")
    loc_key  = f"{lat:.2f},{lon:.2f},m{METHOD}"   # method is part of the key: changing it re-fetches
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
    lines = [f"🕌 Prayer Times — {city}", ""]
    for key in ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]:
        arrow = "  ← next" if key == next_key else ""
        lines.append(f"{PRAYER_NAMES[key]:<10} {format_time(timings[key])}{arrow}")
    return "\n".join(lines)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    location = get_location()
    if location is None:
        print(json.dumps({
            "text":    "🕌 –",
            "tooltip": "Could not detect your location.\nCheck your internet connection.",
            "class":   "prayer-error",
        }))
        return
    lat, lon, city = location
    timings = fetch_prayer_times(lat, lon)

    if not timings:
        print(json.dumps({
            "text":    "🕌 –",
            "tooltip": "Could not fetch prayer times.\nCheck your internet connection.",
            "class":   "prayer-error",
        }))
        return

    prayer_key, prayer_dt = get_next_prayer(timings)
    now       = datetime.now()
    countdown = format_countdown(prayer_dt - now)

    check_notification(prayer_key, prayer_dt)

    tooltip = build_tooltip(timings, prayer_key, city)

    secs = (prayer_dt - now).total_seconds()
    css  = (
        "prayer-soon"   if secs < 300 else
        "prayer-near"   if secs < 900 else
        "prayer-normal"
    )

    text = f"🕌 {PRAYER_NAMES[prayer_key]} {countdown}       --"

    print(json.dumps({
        "text":    text,
        "tooltip": tooltip,
        "class":   css,
    }))


if __name__ == "__main__":
    main()
