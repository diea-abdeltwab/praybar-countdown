<div align="center">

![Header](https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12&height=200&section=header&text=🕌%20praybar&fontSize=60&fontColor=ffffff&animation=fadeIn&fontAlignY=35&desc=Prayer%20Times,%20Everywhere%20You%20Are&descAlignY=55&descSize=18)

### *One project, two homes: your Linux status bar and your phone's home screen.*

[![License](https://img.shields.io/badge/License-MIT-7A2E2E?style=for-the-badge)](LICENSE)
[![Made in Egypt](https://img.shields.io/badge/Made%20in-Egypt%20🇪🇬-0F2238?style=for-the-badge)](https://github.com/diea-abdeltwab)

</div>

---

## 🕋 About

**praybar** is a small family of prayer-time tools built around the same idea: a live countdown to the next prayer, right where you're already looking — with accurate auto-detected location, a full daily schedule, and azan playback.

| Platform | What it is | Docs |
|---|---|---|
| 🐧 **Linux (Waybar )** | A [Waybar](https://github.com/Alexays/Waybar) module — countdown in your status bar, tooltip with the full schedule | [`linux/README.md`](linux/README.md) |
| 🐧 **Linux (Quickshell)** | The same countdown, ported to Quattro's new Quickshell bar via a custom `shell.json` command module | [`omarchy-quatto/README.md`](omarchy4/README.md) |
| 📱 **Android** | A home-screen widget (3 sizes) + standalone app, with scheduled azan alarms | [`android/README.md`](android/README.md) |

Not sure which Linux folder you need? If `~/.config/omarchy/shell.json` exists (or `omarchy --version` says 4.x), you're on Quattro → use `omarchy4/`. If you have `~/.config/waybar/config.jsonc`, use `linux/`.

All three share the same core idea — accurate, low-maintenance auto-location and a distraction-free countdown — built independently for each platform's/bar's native tooling.

<div align="center">

<img src="linux/screenshots/praybar-linux-1.png" width="220"/>&nbsp;&nbsp;<img src="android/screenshots/praybar-android-1.jpg" width="150"/>&nbsp;&nbsp;<img src="android/screenshots/praybar-android-2.jpg" width="150"/>

*Left: the Waybar module · Right: the Android widgets and app*

</div>

---

## 📦 Repository Structure

```
praybar/
├── linux/      ← Waybar module (Omarchy 3 / any Waybar setup)
│   └── screenshots/
├── omarchy4/   ← Quickshell "command" module (Omarchy 4 "Quattro")
├── android/    ← Prayer Countdown app + widget (APK + source)
│   └── screenshots/
├── LICENSE
└── README.md   ← you are here
```

Jump to whichever platform you need:
- **Using Linux + Waybar (or Omarchy 3)?** → [`linux/README.md`](linux/README.md)
- **Using Omarchy 4 "Quattro"?** → [`omarchy4/README.md`](omarchy4/README.md)
- **Want it on your phone?** → [`android/README.md`](android/README.md)

---

## 📜 License

Released under the [MIT License](LICENSE) — applies to both the Linux and Android components.

---

<div align="center">

### 🤝 Built by [Diea Abdeltwab](https://github.com/diea-abdeltwab)

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/diea-abdeltwab/)
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/diea-abdeltwab)

![Footer](https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12&height=100&section=footer)

</div>
