#!/usr/bin/env python3
"""
praybar backend for the GNOME Shell extension.

Resolves the location, fetches (and caches) today's prayer timings from the
Aladhan API and prints ONE JSON document to stdout. It has no UI and no
side effects besides its cache files, so the extension can call it as often
as it likes. Countdown, notifications and azan playback live in the extension.

Success:
  {"ok": true, "city": "...", "date": "YYYY-MM-DD", "timings": {"Fajr": "04:54", ...},
   "tomorrow_fajr": "04:55" | null, "source": "geoclue|wttr|ip|cache", "stale": false}
Failure:
  {"ok": false, "error": "..."}

Location is ALWAYS auto-detected, best source first:
  1. GeoClue (GNOME's own location service, via its `where-am-i` demo tool).
     It uses Wi-Fi/GeoIP data from BeaconDB and is typically much closer than
     a plain IP lookup, which only knows the city your ISP is registered in.
  2. wttr.in IP geolocation.   3. Generic IP lookups (ipapi.co, ip-api.com).
The location is re-detected once per calendar day, together with that day's
timings, so a change of city is picked up the next night with no
configuration. If every lookup fails the last known location is reused; with
no history at all there is no guess - the result is an error, never times for
the wrong city. (The old Mozilla Location Service tier is gone: Mozilla
retired it in 2024.)
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "praybar"
LOCATION_CACHE = CACHE_DIR / "location.json"
TIMINGS_CACHE = CACHE_DIR / "timings.json"

# A fresh reading within this many degrees (~5 km) of the cached one is treated
# as "same place" and the OLD coordinates are kept. The timings cache is keyed
# on rounded lat/lon, so jitter here would otherwise force a re-fetch with
# slightly different coordinates and make prayer times drift by a minute.
JITTER_TOLERANCE_DEG = 0.05

TIER_CONFIDENCE = {"geoclue": 3, "wttr": 2, "ip": 1}

GEOCLUE_TIMEOUT_S = 10
# GeoClue reports its own accuracy radius. ~25 km is typical for GeoIP, which is
# still city-level and fine for prayer times; beyond ~50 km it is a country or
# region centroid and worse than the other tiers, so it is rejected.
GEOCLUE_MAX_ACCURACY_M = 50_000
WHERE_AM_I_GLOBS = (
    "/usr/libexec/geoclue-2.0/demos/where-am-i",       # Fedora, Debian/Ubuntu
    "/usr/lib*/geoclue-2.0/demos/where-am-i",          # Arch and multiarch layouts
    "/usr/lib/*/geoclue-2.0/demos/where-am-i",
)
PRAYER_KEYS = ("Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha")
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) praybar-gnome/1.0"


def _get_json(url, timeout, headers=None):
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _write_json_atomic(path, data):
    """Write via temp file + rename so a crash never leaves a half-written cache."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data))
    os.replace(tmp, path)


# ─── Location ────────────────────────────────────────────────────────────────

def _find_where_am_i():
    """Path of GeoClue's `where-am-i` demo tool, or None if it is not installed."""
    for pattern in WHERE_AM_I_GLOBS:
        for path in sorted(glob.glob(pattern)):
            if os.access(path, os.X_OK):
                return path
    return shutil.which("where-am-i")


_NUMBER = r"(-?\d+(?:[.,]\d+)?)"
_LOCATION_RE = re.compile(
    rf"Latitude:\s*{_NUMBER}\s*°?\s*\n\s*Longitude:\s*{_NUMBER}\s*°?\s*\n\s*Accuracy:\s*{_NUMBER}\s*meters"
)


def parse_where_am_i(output):
    """
    Parse `where-am-i` output into (lat, lon, accuracy_m) from the LAST
    reported location (GeoClue refines its fix, so the last one is the best),
    or None if there is none or it is too coarse to be useful.
    """
    blocks = _LOCATION_RE.findall(output)
    if not blocks:
        return None
    lat, lon, accuracy = (float(v.replace(",", ".")) for v in blocks[-1])  # tolerate locale commas
    if accuracy > GEOCLUE_MAX_ACCURACY_M:
        return None
    return lat, lon, accuracy


def _reverse_geocode(lat, lon):
    """Best-effort 'City, CC' label for a coordinate via OpenStreetMap Nominatim."""
    try:
        data = _get_json(
            f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
            "&zoom=10&accept-language=en", 6)
        addr = data.get("address", {})
        city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county") or ""
        label = f'{city}, {addr.get("country_code", "").upper()}'.strip(", ")
        return label or None
    except Exception:  # noqa: BLE001 - a label is optional
        return None


def _geoclue_geolocate():
    """
    Ask GeoClue for the location. Needs the `where-am-i` tool and GNOME's
    Location Services switched on; if either is missing this simply returns
    None and the next tier is used.
    """
    exe = _find_where_am_i()
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "-t", str(GEOCLUE_TIMEOUT_S)], capture_output=True, text=True,
            timeout=GEOCLUE_TIMEOUT_S + 5, env={**os.environ, "LC_ALL": "C"},
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    fix = parse_where_am_i(out)
    if not fix:
        return None
    lat, lon, _accuracy = fix
    return lat, lon, _reverse_geocode(lat, lon) or f"{lat:.2f}, {lon:.2f}"


def _wttr_geolocate():
    try:
        data = _get_json("https://wttr.in/?format=j1", 8, {"User-Agent": "curl/8.0"})
        area = data["nearest_area"][0]
        city = area["areaName"][0]["value"]
        country = area.get("country", [{}])[0].get("value", "")
        return float(area["latitude"]), float(area["longitude"]), f"{city}, {country}".strip(", ")
    except Exception:
        return None


def _ip_geolocate():
    providers = (
        ("https://ipapi.co/json/",
         lambda d: (float(d["latitude"]), float(d["longitude"]),
                    f'{d.get("city", "")}, {d.get("country_code", "")}'.strip(", "))),
        ("http://ip-api.com/json/",
         lambda d: (float(d["lat"]), float(d["lon"]),
                    f'{d.get("city", "")}, {d.get("countryCode", "")}'.strip(", "))),
    )
    for url, parse in providers:
        try:
            return parse(_get_json(url, 6))
        except Exception:
            continue
    return None


def accept_reading(lat, lon, city, source, cached):
    """
    Apply jitter tolerance + confidence ranking against the last cached fix.
    Returns (lat, lon, city, source). A weaker tier disagreeing with a stronger
    one is treated as that lookup being wrong this once, not as the user moving.
    """
    if not cached:
        return lat, lon, city, source

    same_place = (
        abs(cached.get("lat", 999) - lat) <= JITTER_TOLERANCE_DEG
        and abs(cached.get("lon", 999) - lon) <= JITTER_TOLERANCE_DEG
    )
    old_conf = TIER_CONFIDENCE.get(cached.get("source"), 0)
    new_conf = TIER_CONFIDENCE.get(source, 0)
    keep_old = (cached["lat"], cached["lon"], cached["city"], cached.get("source", source))

    if same_place:
        return (*keep_old[:3], source if new_conf > old_conf else keep_old[3])
    if new_conf < old_conf:
        return keep_old
    return lat, lon, city, source  # equal/higher confidence disagrees: genuine move


def resolve_location(today):
    """
    Return (lat, lon, city, source), or None if the location is unknown.
    A cached fix is valid only for the day it was made, so the first run
    after midnight looks the location up again.
    """
    cached = _read_json(LOCATION_CACHE)
    if cached and cached.get("date") == today.isoformat():
        return cached["lat"], cached["lon"], cached["city"], cached.get("source", "cache")

    for source, probe in (("geoclue", _geoclue_geolocate), ("wttr", _wttr_geolocate), ("ip", _ip_geolocate)):
        fix = probe()
        if fix:
            lat, lon, city, src = accept_reading(*fix, source, cached)
            # Written even when a downgrade was rejected, so today's lookup
            # is not repeated on every call.
            _write_json_atomic(LOCATION_CACHE, {
                "lat": lat, "lon": lon, "city": city, "source": src, "date": today.isoformat(),
            })
            return lat, lon, city, src

    if cached:  # lookups failed: keep the last known city instead of guessing
        return cached["lat"], cached["lon"], cached["city"], "cache"
    return None


# ─── Prayer timings ──────────────────────────────────────────────────────────

def _fetch_day(day, lat, lon, method):
    url = (
        f"https://api.aladhan.com/v1/timings/{day.strftime('%d-%m-%Y')}"
        f"?latitude={lat}&longitude={lon}&method={method}"
    )
    last_error = None
    for _ in range(3):  # retry the SAME location; never fall back to another city
        try:
            raw = _get_json(url, 8)["data"]["timings"]
            return {k: raw[k][:5] for k in PRAYER_KEYS}  # API may append " (EET)"
        except Exception as exc:  # noqa: BLE001 - any failure just means "try again"
            last_error = exc
    raise RuntimeError(f"Aladhan request failed: {last_error}")


def load_timings(lat, lon, method, today):
    """
    Return (today_timings, tomorrow_fajr_or_None, stale).
    Cache layout: {"key": "lat,lon,method", "days": {"YYYY-MM-DD": {...timings}}}.
    The key includes the calculation method, so changing it in the preferences
    takes effect immediately instead of serving the old method's times.
    """
    key = f"{lat:.2f},{lon:.2f},{method}"
    cache = _read_json(TIMINGS_CACHE)
    days = cache["days"] if cache and cache.get("key") == key else {}
    today_iso, tomorrow = today.isoformat(), today + timedelta(days=1)
    changed = False

    if today_iso not in days:
        try:
            days[today_iso] = _fetch_day(today, lat, lon, method)
            changed = True
        except RuntimeError:
            if not days:
                raise
            # Offline: show the most recent cached day, flagged as stale.
            newest = max(days)
            return days[newest], None, True

    if tomorrow.isoformat() not in days:
        try:
            days[tomorrow.isoformat()] = _fetch_day(tomorrow, lat, lon, method)
            changed = True
        except RuntimeError:
            pass  # optional: the extension falls back to today's Fajr

    if changed:
        days = {d: t for d, t in days.items() if d >= today_iso}  # prune the past
        _write_json_atomic(TIMINGS_CACHE, {"key": key, "days": days})

    tomorrow_fajr = days.get(tomorrow.isoformat(), {}).get("Fajr")
    return days[today_iso], tomorrow_fajr, False


# ─── Entry point ─────────────────────────────────────────────────────────────

def build_result(method, today=None):
    today = today or date.today()
    location = resolve_location(today)
    if location is None:
        raise RuntimeError("Could not detect your location - check your internet connection")
    lat, lon, city, source = location
    timings, tomorrow_fajr, stale = load_timings(lat, lon, method, today)
    return {
        "ok": True, "city": city, "date": today.isoformat(), "timings": timings,
        "tomorrow_fajr": tomorrow_fajr, "source": source, "stale": stale,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="praybar prayer-times backend")
    parser.add_argument("--method", type=int, default=5)
    args = parser.parse_args(argv)

    try:
        result = build_result(args.method)
    except Exception as exc:  # noqa: BLE001 - the extension needs JSON, never a traceback
        result = {"ok": False, "error": str(exc)}
    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
