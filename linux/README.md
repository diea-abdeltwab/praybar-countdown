<div align="center">

![Header](https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12&height=200&section=header&text=🕌%20praybar&fontSize=60&fontColor=ffffff&animation=fadeIn&fontAlignY=35&desc=Prayer%20Times,%20right%20in%20your%20Waybar&descAlignY=55&descSize=18)

### *Reliable prayer-time countdowns for your Linux status bar — no drift, no guesswork.*

[![Shell](https://img.shields.io/badge/Bash-4EAA25?style=for-the-badge&logo=gnubash&logoColor=white)](https://www.gnu.org/software/bash/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Waybar](https://img.shields.io/badge/Waybar-1793D1?style=for-the-badge&logo=wayland&logoColor=white)](https://github.com/Alexays/Waybar)
[![License](https://img.shields.io/badge/License-MIT-7A2E2E?style=for-the-badge)](#-license)
[![Made in Egypt](https://img.shields.io/badge/Made%20in-Egypt%20🇪🇬-0F2238?style=for-the-badge)](https://github.com/diea-abdeltwab)

[![Typing SVG](https://readme-typing-svg.herokuapp.com?font=Fira+Code&weight=600&size=20&duration=2800&pause=900&color=7A2E2E&background=00000000&center=true&vCenter=true&width=650&lines=Street-level+location+%E2%80%94+no+manual+setup;Caches+smartly%2C+never+drifts+minute+to+minute;Amber+%E2%86%92+red+%E2%86%92+azan+as+the+time+gets+close)](https://git.io/typing-svg)

</div>

---

## 🕋 About

**praybar** is a lightweight [Waybar](https://github.com/Alexays/Waybar) module that shows a live countdown to the next prayer, right in your status bar — with a tooltip for the full daily schedule, desktop notifications, and an azan sound when the time comes.

> 📱 Want this on your phone instead? See the [Android version](../android/README.md).

It auto-detects your location from your IP, calculates accurate timings via the [Aladhan API](https://aladhan.com/prayer-times-api), and caches everything sensibly so it stays fast, quiet on your network, and — most importantly — **stable**. No random minute-to-minute drift, no re-fetching on every tick.

<div align="center">

| ⏱️ Live Countdown | 🔔 Notifications + Azan | 🧭 Auto Location | 🕌 Full Tooltip Schedule |
|:---:|:---:|:---:|:---:|
| Bar text updates every tick | Fires once per prayer, ±90s window | Wi-Fi → wttr.in → IP, confidence-guarded | Fajr → Isha, next prayer highlighted |

</div>

---

## 📸 Preview

<div align="center">

| Normal | Getting close | Final countdown | Azan notification |
|:---:|:---:|:---:|:---:|
| <img src="screenshots/praybar-linux-1.png" width="220"/> | <img src="screenshots/praybar-linux-2.png" width="220"/> | <img src="screenshots/praybar-linux-3.png" width="220"/> | <img src="screenshots/praybar-linux-4.png" width="280"/> |
| Bar segment + full tooltip | Text turns amber under 15 min | Text turns red and blinks under 5 min | Native notification when it's time |

</div>

The tooltip always shows the full day at a glance, with the next prayer marked:

```text
🕌 Prayer Times — El Faiyum, Egypt
Fajr        04:54
Sunrise     06:27
Dhuhr       13:01
Asr         16:36
Maghrib     19:34   ← next
Isha        20:56
```

---

## ✨ Features

- 🌍 **Automatic, accurate location detection** — scans nearby Wi-Fi APs (like phones/browsers do) for street-level accuracy, then falls back to `wttr.in`'s IP geolocation (the same backend Omarchy's weather widget uses) if no Wi-Fi adapter is available — no config needed, and works well while traveling
- 🎯 **Jitter-tolerant caching** — a fresh location reading within ~5 km of the last known spot is treated as "no change," so timings never shift for no reason
- ⏰ **Daily refresh at 12:00** — a `systemd` user timer keeps the cache fresh on a predictable schedule, independent of Waybar's own polling
- 🔔 **Native notifications + azan playback** — fires once per prayer, with a dismiss action
- 🎨 **Color-coded urgency** — text shifts color as a prayer approaches, and blinks in the final stretch
- 📍 **Manual override** — pin exact coordinates if you don't want to rely on IP geolocation
- 🗑️ **Clean uninstall** — one script fully reverts your Waybar config and removes all traces

---

## 📦 Installation

### Prerequisites

| Requirement | Purpose |
|---|---|
| `python3` | Runs the module script |
| `waybar` | Displays the module |
| `notify-send` (libnotify ≥ 0.8) | Desktop notifications |
| `mpv` or `paplay` *(optional)* | Azan playback |

### Steps

```bash
git clone https://github.com/diea-abdeltwab/praybar.git
cd praybar/linux
chmod +x install.sh
./install.sh
# → walks you through the 9 steps below, then restarts Waybar with the module live
```

The installer will:

1. ✅ Check dependencies
2. 💾 Back up your current Waybar config
3. 🕐 Ask whether you want **12-hour** or **24-hour** time in the tooltip
4. 📍 Ask whether to **auto-detect** your location or enter **exact coordinates** manually (recommended if this machine has no Wi-Fi adapter)
5. 📁 Copy `praybar.py` and its stylesheet into `~/.config/waybar/`
6. ⚙️ Patch `config` / `config.jsonc` and `style.css` automatically
7. 🔊 Fetch a default azan sound (or use the bundled one)
8. ⏰ Install a `systemd` timer for a daily refresh at 12:00
9. 🔄 Restart Waybar

---

## 🗑️ Uninstall

```bash
./uninstall.sh
# → removes the module + the daily refresh timer, and restores your original Waybar config from backup
```

---

## ⚙️ Configuration

Open `~/.config/waybar/praybar.py` and adjust the constants near the top:

```python
METHOD = 5   # Egyptian General Authority of Survey
```

| ID | Authority |
|:---:|---|
| 3 | Muslim World League |
| 4 | Umm Al-Qura (Mecca) |
| **5** | **Egyptian General Authority of Survey** *(default)* |
| 2 | ISNA (North America) |
| 9 | Kuwait |

<details>
<summary><b>Manual location (skip Wi-Fi/IP detection entirely)</b></summary>

Set this during `./install.sh` (option 2 when asked), or edit directly any time:

```python
MANUAL_LATITUDE  = 29.3084   # your latitude
MANUAL_LONGITUDE = 30.8428   # your longitude
MANUAL_CITY      = "Fayoum, EG"
```

If your machine has no Wi-Fi adapter (desktop with only Ethernet, VM, etc.), auto-detect will always fall back to IP-based geolocation — manual coordinates are the only way to get exact accuracy in that case.

</details>

<details>
<summary><b>Time format</b></summary>

Chosen once during `./install.sh` (12h or 24h), but changeable anytime:

```python
TIME_FORMAT = "24h"   # "13:05"
TIME_FORMAT = "12h"   # "1:05 PM"
```

</details>

---

## 🧠 How the caching works

| Layer | Refresh trigger | Why |
|---|---|---|
| **Wi-Fi positioning** | On every location refresh | Street-level accuracy via Mozilla's Wi-Fi positioning database — no reliance on your ISP's registered city |
| **wttr.in geolocation** | If no Wi-Fi APs are found | Same IP2Location/MaxMind backend Omarchy's weather widget uses — noticeably more accurate per-ISP than generic IP lookups |
| **Generic IP geolocation** | Only if wttr.in is unreachable | Last-resort fallback (ipapi.co, then ip-api.com) |
| **Confidence guard** | Every time a *different* location comes back | A weaker tier (e.g. generic IP) disagreeing with what a stronger tier (Wi-Fi/wttr.in) previously found is treated as that lookup failing this once — not as you having moved — so the last known good fix is kept |
| **Location cache** | Every 24h, *or* daily 12:00 timer | Avoids hammering any provider |
| **Jitter filter** | Ignores location changes < ~5 km | Stops positioning noise from being mistaken for travel |
| **Timings cache** | Only when date or *accepted* location changes | Keeps prayer times stable day to day |

<details>
<summary><b>Why Wi-Fi + wttr.in instead of a single IP lookup</b></summary>

Wi-Fi positioning needs a scan tool — `nmcli` (NetworkManager), `iw`, or `iwlist` (at least one is usually preinstalled) — and at least 2 nearby access points. On machines without a Wi-Fi adapter (desktops, VMs), praybar automatically falls back to `wttr.in`'s IP geolocation, which is considerably more accurate per-ISP than generic providers — this is what makes fully automatic detection reliable even while traveling.

`wttr.in` is a free community service and occasionally rate-limited or slow; when that happens, the confidence guard above stops the resulting weaker fallback reading from silently overwriting your last good location. `MANUAL_LATITUDE` / `MANUAL_LONGITUDE` remain available for anyone who wants a fixed, guaranteed-exact location regardless.

</details>

---

## 🩺 Troubleshooting

<details>
<summary><strong>Times look slightly off from my exact area</strong></summary>
<br>

If Wi-Fi positioning isn't available on your machine, praybar falls back to `wttr.in`'s IP geolocation, which is already considerably more accurate than generic providers — but any IP-based method can occasionally be a city off. Set `MANUAL_LATITUDE` / `MANUAL_LONGITUDE` for a guaranteed-exact fix.

</details>

<details>
<summary><strong>No azan sound plays</strong></summary>
<br>

Install `mpv` or `paplay`, or drop your own file at `~/.config/waybar/azan.mp3`.

</details>

<details>
<summary><strong>Module doesn't appear in Waybar</strong></summary>
<br>

Re-run `./install.sh` — step 4 patches your config automatically. Check that `custom/praybar` appears in your modules list in `~/.config/waybar/config.jsonc`.

</details>

---

## 🏗️ Project Structure

```text
praybar/
├── praybar.py                    # main module script
├── install.sh                    # installer
├── uninstall.sh                  # clean removal
├── assets/
│   ├── praybar-style.css         # Waybar styling
│   └── azan.mp3                  # default azan sound
├── scripts/
│   └── patch_waybar.py           # config.jsonc / style.css patcher
├── systemd/
│   ├── praybar-refresh.service   # daily fetch job
│   └── praybar-refresh.timer     # fires at 12:00 daily
└── screenshots/                  # README preview images
```

---

## 📜 License

Released under the [MIT License](../LICENSE) (applies to the whole `praybar` project, including the [Android app](../android/README.md)).

---

<div align="center">

### 🤝 Built by [Diea Abdeltwab](https://github.com/diea-abdeltwab)

*Data Engineer · Software Engineer · Turning raw data into reliable systems*

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/diea-abdeltwab/)
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/diea-abdeltwab)

⭐ **If this saved you from missing a prayer, consider starring the repo!** ⭐

![Footer](https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12&height=100&section=footer)

</div>
