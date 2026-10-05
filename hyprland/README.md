<div align="center">

![Header](https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12&height=200&section=header&text=🕌%20praybar&fontSize=60&fontColor=ffffff&animation=fadeIn&fontAlignY=35&desc=Prayer%20Times,%20right%20in%20your%20Waybar&descAlignY=55&descSize=18)

### *Reliable prayer-time countdowns for your Linux status bar — no drift, no guesswork.*

[![Shell](https://img.shields.io/badge/Bash-4EAA25?style=for-the-badge&logo=gnubash&logoColor=white)](https://www.gnu.org/software/bash/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Waybar](https://img.shields.io/badge/Waybar-1793D1?style=for-the-badge&logo=wayland&logoColor=white)](https://github.com/Alexays/Waybar)
[![License](https://img.shields.io/badge/License-MIT-7A2E2E?style=for-the-badge)](#-license)
[![Made in Egypt](https://img.shields.io/badge/Made%20in-Egypt%20🇪🇬-0F2238?style=for-the-badge)](https://github.com/diea-abdeltwab)

[![Typing SVG](https://readme-typing-svg.herokuapp.com?font=Fira+Code&weight=600&size=20&duration=2800&pause=900&color=7A2E2E&background=00000000&center=true&vCenter=true&width=650&lines=Automatic+location+%E2%80%94+zero+setup;Caches+smartly%2C+never+drifts+minute+to+minute;Amber+%E2%86%92+red+%E2%86%92+azan+as+the+time+gets+close)](https://git.io/typing-svg)

</div>

---

## 🕋 About

**praybar** is a lightweight [Waybar](https://github.com/Alexays/Waybar) module that shows a live countdown to the next prayer, right in your status bar — with a tooltip for the full daily schedule, desktop notifications, and an azan sound when the time comes.

> 📱 Want this on your phone instead? See the [Android version](../android/README.md).

It auto-detects your location from your IP, calculates accurate timings via the [Aladhan API](https://aladhan.com/prayer-times-api), and caches everything sensibly so it stays fast, quiet on your network, and — most importantly — **stable**. No random minute-to-minute drift, no re-fetching on every tick.

<div align="center">

| ⏱️ Live Countdown | 🔔 Notifications + Azan | 🧭 Auto Location | 🕌 Full Tooltip Schedule |
|:---:|:---:|:---:|:---:|
| Bar text updates every tick | Fires once per prayer, ±90s window | wttr.in → IP, confidence-guarded, re-detected nightly | Fajr → Isha, next prayer highlighted |

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
🕌 Prayer Times — Your City, Country
Fajr        04:54
Sunrise     06:27
Dhuhr       13:01
Asr         16:36
Maghrib     19:34   ← next
Isha        20:56
```

---

## ✨ Features

- 🌍 **Automatic location detection** — `wttr.in`'s IP geolocation (the same backend Omarchy's weather widget uses), with generic IP lookups as a fallback — no config needed, and it works while traveling because the location is re-checked every night
- 🎯 **Jitter-tolerant caching** — a fresh location reading within ~5 km of the last known spot is treated as "no change," so timings never shift for no reason
- ⏰ **Daily refresh at midnight** — a `systemd` user timer fires at 00:00 and re-detects your location together with the new day's timings, so travelling needs no setup — independent of Waybar's own polling
- 🔔 **Native notifications + azan playback** — fires once per prayer, with a dismiss action
- 🎨 **Color-coded urgency** — text shifts color as a prayer approaches, and blinks in the final stretch
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
git clone https://github.com/diea-abdeltwab/praybar-countdown.git
cd praybar-countdown/linux
chmod +x install.sh
./install.sh
# → walks you through the 9 steps below, then restarts Waybar with the module live
```

The installer will:

1. ✅ Check dependencies
2. 💾 Back up your current Waybar config
3. 🕐 Ask whether you want **12-hour** or **24-hour** time in the tooltip
4. 📍 Show the location it detected (always automatic — nothing to enter)
5. 📁 Copy `praybar.py` and its stylesheet into `~/.config/waybar/`
6. ⚙️ Patch `config` / `config.jsonc` and `style.css` automatically
7. 🔊 Fetch a default azan sound (or use the bundled one)
8. ⏰ Install a `systemd` timer for a daily refresh at 00:00
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
| **wttr.in geolocation** | On the nightly location refresh | Same IP2Location/MaxMind backend Omarchy's weather widget uses — noticeably more accurate per-ISP than generic IP lookups |
| **Generic IP geolocation** | Only if wttr.in is unreachable | Last-resort fallback (ipapi.co, then ip-api.com) |
| **Confidence guard** | Every time a *different* location comes back | A weaker tier (e.g. generic IP) disagreeing with what a stronger tier (wttr.in) previously found is treated as that lookup failing this once — not as you having moved — so the last known good fix is kept |
| **Location cache** | Once per calendar day — the first run after 00:00 (the daily timer) | Re-detects where you are every night, without hammering any provider |
| **Jitter filter** | Ignores location changes < ~5 km | Stops positioning noise from being mistaken for travel |
| **Timings cache** | Only when date or *accepted* location changes | Keeps prayer times stable day to day |

<details>
<summary><b>Why wttr.in first, and what happened to Wi-Fi positioning?</b></summary>

`wttr.in`'s IP geolocation is considerably more accurate per-ISP than generic providers, so it goes first; `ipapi.co` / `ip-api.com` are the fallback. An earlier version also scanned nearby Wi-Fi access points and asked Mozilla Location Service for a street-level fix, but Mozilla retired that service in 2024, so the tier could never succeed and was removed.

`wttr.in` is a free community service and occasionally rate-limited or slow; when that happens, the confidence guard above stops the resulting weaker fallback reading from silently overwriting your last good location. If every lookup fails, the last known location is kept; with no history at all praybar shows an error instead of guessing a city.

</details>

---

## 🩺 Troubleshooting

<details>
<summary><strong>Times look slightly off from my exact area</strong></summary>
<br>

Location comes from IP geolocation (`wttr.in` first), which is already considerably more accurate than generic providers — but any IP-based method can occasionally land on your ISP's regional hub instead of your own town. The location is re-checked every night at 00:00, so it corrects itself when the provider's answer does.

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
│   └── praybar-refresh.timer     # fires at 00:00 daily
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
