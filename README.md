<div align="center">

![Header](https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12&height=200&section=header&text=🕌%20praybar&fontSize=60&fontColor=ffffff&animation=fadeIn&fontAlignY=35&desc=Prayer%20Times,%20Everywhere%20You%20Are&descAlignY=55&descSize=18)

### *One project, two homes: your Linux status bar and your phone's home screen.*

[![Linux](https://img.shields.io/badge/Linux-Waybar-1793D1?style=for-the-badge&logo=linux&logoColor=white)](linux/README.md)
[![Android](https://img.shields.io/badge/Android-Kotlin-3DDC84?style=for-the-badge&logo=android&logoColor=white)](android/README.md)
[![License](https://img.shields.io/badge/License-MIT-7A2E2E?style=for-the-badge)](LICENSE)
[![Made in Egypt](https://img.shields.io/badge/Made%20in-Egypt%20🇪🇬-0F2238?style=for-the-badge)](https://github.com/diea-abdeltwab)

[![Typing SVG](https://readme-typing-svg.herokuapp.com?font=Fira+Code&weight=600&size=20&duration=2800&pause=900&color=7A2E2E&background=00000000&center=true&vCenter=true&width=650&lines=Auto-detected+location+%E2%80%94+no+city+picker;A+live+countdown+to+the+next+prayer;Full+azan%2C+wherever+you+set+it+up)](https://git.io/typing-svg)

</div>

---

## 🕋 About

**praybar** is a small family of prayer-time tools built around the same idea: a live countdown to the next prayer, right where you're already looking — with accurate auto-detected location, a full daily schedule, and azan playback.

| Platform | What it is | Docs |
|---|---|---|
| 🐧 **Linux** | A [Waybar](https://github.com/Alexays/Waybar) module — countdown in your status bar, tooltip with the full schedule | [`linux/README.md`](linux/README.md) |
| 📱 **Android** | A home-screen widget (3 sizes) + standalone app, with scheduled azan alarms | [`android/README.md`](android/README.md) |

Both share the same core idea — accurate, low-maintenance auto-location and a distraction-free countdown — but each is built independently, using each platform's native tooling (no shared codebase, no cross-compiled hacks).

<div align="center">

<img src="linux/screenshots/praybar-linux-1.png" width="220"/>&nbsp;&nbsp;<img src="android/screenshots/praybar-android-1.jpg" width="150"/>&nbsp;&nbsp;<img src="android/screenshots/praybar-android-2.jpg" width="150"/>

*Left: the Waybar module · Right: the Android widgets and app*

</div>

---

## 🤝 What both versions share

- 🌍 **Automatic location + country-aware calculation method** — no manual city/method picker, resolves the right calculation authority for wherever you are
- ⏳ **Live countdown**, always visible, to whichever prayer is next
- 🔔 **Azan playback** at the exact prayer time, not just a silent notification
- 🟠 **Visual urgency cue** as the next prayer gets close
- 📴 **Graceful offline behavior** — falls back to the last successfully fetched schedule

<details>
<summary><b>Where they differ</b></summary>

| | Linux (Waybar) | Android |
|---|---|---|
| Surface | Status bar module + tooltip | Home-screen widget (3 sizes) + app |
| Azan delivery | Triggered by the module while running | Scheduled `AlarmManager` alarms — rings even if the app is closed |
| Persistence | Runs as long as Waybar runs | Boot receiver re-arms today's alarms after a restart |
| Language toggle | — | Arabic / English, in-app |
| Install | `install.sh` / `uninstall.sh` | Prebuilt APK, or build from source |

</details>

---

## 📦 Repository Structure

```text
praybar/
├── linux/      ← Waybar module (install.sh / uninstall.sh)
│   └── screenshots/
├── android/    ← Prayer Countdown app + widget (APK + source)
│   └── screenshots/
├── LICENSE
└── README.md   ← you are here
```

Jump to whichever platform you need:

- **Using Linux + Waybar?** → [`linux/README.md`](linux/README.md)
- **Want it on your phone?** → [`android/README.md`](android/README.md)

---

## 📜 License

Released under the [MIT License](LICENSE) — applies to both the Linux and Android components.

---

<div align="center">

### 🤝 Built by [Diea Abdeltwab](https://github.com/diea-abdeltwab)

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/diea-abdeltwab/)
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/diea-abdeltwab)

⭐ **If this keeps you on time for prayer, a star helps a lot!** ⭐

![Footer](https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12&height=100&section=footer)

</div>
