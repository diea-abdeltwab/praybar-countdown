<div align="center">

![Header](https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12&height=200&section=header&text=🕌%20praybar&fontSize=60&fontColor=ffffff&animation=fadeIn&fontAlignY=35&desc=Prayer%20Times,%20on%20Omarchy%204%20%2F%20Quickshell&descAlignY=55&descSize=16)

### *The same reliable prayer-time countdown — ported for Omarchy 4 "Quattro"'s new Quickshell bar.*

[![Shell](https://img.shields.io/badge/Bash-4EAA25?style=for-the-badge&logo=gnubash&logoColor=white)](https://www.gnu.org/software/bash/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Quickshell](https://img.shields.io/badge/Quickshell-3E5C76?style=for-the-badge&logo=wayland&logoColor=white)](https://quickshell.org/)
[![Omarchy 4](https://img.shields.io/badge/Omarchy-4%20Quattro-1793D1?style=for-the-badge)](https://omarchy.org)
[![License](https://img.shields.io/badge/License-MIT-7A2E2E?style=for-the-badge)](#-license)

[![Made in Egypt](https://img.shields.io/badge/Made%20in-Egypt%20🇪🇬-0F2238?style=for-the-badge)](https://github.com/diea-abdeltwab)

</div>

---

## 🕋 About

This is the **Omarchy 4 ("Quattro") port** of praybar. Omarchy 4 replaced Waybar
(and Walker, Mako, hyprlock, hypridle, swaybg, polkit-gnome, SwayOSD) with a
single long-running [Quickshell](https://quickshell.org/) process — `omarchy-shell`
— that owns the bar, panels, notifications, and lock screen as plugins, configured
through `~/.config/omarchy/shell.json` instead of Waybar's `config.jsonc`.

If you're still on Omarchy 3 (or any other Waybar-based setup), use
[`../linux/`](../linux/README.md) instead — this folder is Quattro-only.

> 📖 Not sure which one you're on? Run `omarchy --version`, or check whether
> `~/.config/omarchy/shell.json` exists (Quattro) vs. `~/.config/waybar/config.jsonc`
> (Omarchy 3 / plain Waybar).

Everything that made the Waybar version reliable — Wi-Fi/`wttr.in`/IP location
detection with a confidence guard, jitter-tolerant caching, azan playback,
dismissible notifications — is **unchanged** in this port. Only the *plumbing*
that gets the countdown onto your bar is different, because Quattro's bar has
no `config.jsonc`/`style.css` to patch anymore.

---

## 🧩 Why this works: Omarchy 4 kept a Waybar-compatible escape hatch

Quattro's bar supports lightweight "command" modules declared inline in
`shell.json`, without writing any QML or building a full shell plugin:

```json
{ "id": "praybar", "type": "command", "exec": "python3 ~/.config/omarchy/bar/scripts/praybar.py", "interval": 30 }
```

The module's stdout contract is documented as **"plain text or Waybar-style
JSON (`{ "text", "tooltip", "class" }`)"** — the exact same shape `praybar.py`
already produced for Waybar. That's the whole reason this port is a plumbing
change rather than a rewrite: the Python script's *output* didn't need to
change, only *where it lives* and *how it gets registered*.

A full Quickshell/QML plugin (a `manifest.json` + `BarWidget.qml` dropped
into `~/.config/omarchy/plugins/`) was the other option, but it buys nothing
here — no popup, no interactive state, just polled text — so the inline
command module is the right-sized tool for this job. See
[`omarchy-shell.md`](https://github.com/basecamp/omarchy/blob/quattro/docs/omarchy-shell.md)
in the Omarchy repo, "Custom bar modules", if you want the full picture
(or want to build something richer, like a click-to-expand panel).

---

## ✨ Features

Identical to the [Waybar version](../linux/README.md#-features) — location
detection, caching strategy, and azan/notification behavior are shared
verbatim:

- 🌍 **Automatic, accurate location detection** — Wi-Fi positioning → `wttr.in` IP geolocation → generic IP geolocation, confidence-guarded so a weaker fallback never silently overwrites a better fix
- 🎯 **Jitter-tolerant caching** — no drift from sub-5km positioning noise
- ⏰ **Daily refresh at 12:00** — a `systemd` user timer, independent of the bar's own polling
- 🔔 **Native notifications + azan playback** — fires once per prayer, dismissible
- 🌙🌅☀️🌤️🌇🌌 **Per-prayer icons** — each prayer gets its own glyph in both the bar and the tooltip, so you recognize which one's next without reading the label; swaps to 🔔 in the final 5 minutes as a guaranteed urgency cue (see [Design notes](#-design-notes--whats-confirmed-vs-best-effort))
- 📍 **Manual override** — pin exact coordinates if you'd rather not rely on IP geolocation
- 🗑️ **Clean uninstall** — one script fully reverts `shell.json` and removes all traces

---

## 📦 Installation

### Prerequisites

| Requirement | Purpose |
|---|---|
| Omarchy **4.x ("Quattro")** | Provides the Quickshell bar this module plugs into |
| `python3` | Runs the module script |
| `notify-send` (libnotify ≥ 0.8) | Desktop notifications — Quattro's shell now plays the notification-daemon role Mako used to, so this should keep working unchanged |
| `mpv` or `paplay` *(optional)* | Azan playback |

### Steps

```bash
git clone https://github.com/diea-abdeltwab/praybar.git
cd praybar/omarchy4
chmod +x install.sh
./install.sh
```

The installer will:
1. ✅ Sanity-check that this actually looks like an Omarchy 4 system
2. 🔍 Check dependencies
3. 💾 Back up your current `shell.json` (if you have one)
4. 🕐 Ask **12-hour** or **24-hour** time in the tooltip
5. 📍 Ask **auto-detect** or **manual coordinates**
6. 📁 Copy `praybar.py` into `~/.config/omarchy/bar/scripts/`
7. ⚙️ Patch `shell.json` — inserts the module just before the clock widget
8. 🔊 Fetch a default azan sound (or use the bundled one)
9. ⏰ Install a `systemd` timer for a daily refresh at 12:00
10. 🔄 Reload the running shell (`omarchy-shell shell reloadConfig`, live — no restart needed)

---

## 🗑️ Uninstall

```bash
./uninstall.sh
```

Removes the module, the daily refresh timer, and restores your original
`shell.json` from backup (or surgically removes just the `praybar` entry if
you'd rather keep everything else you've customized since).

---

## ⚙️ Configuration

Open `~/.config/omarchy/bar/scripts/praybar.py` and adjust the constants near
the top — this is the same file, same options, as the Waybar version:

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

```python
MANUAL_LATITUDE  = 29.3084   # your latitude
MANUAL_LONGITUDE = 30.8428   # your longitude
MANUAL_CITY      = "Fayoum, EG"

TIME_FORMAT = "24h"   # or "12h"
```

Want it somewhere other than right before the clock? Open `~/.config/omarchy/shell.json`
and move the `"id": "praybar"` entry between `bar.layout.left` / `.center` / `.right` by
hand, or use Quattro's drag-to-move bar UI once it's on the bar.

---

## 🩺 Troubleshooting

<details>
<summary><strong>The installer says this doesn't look like Omarchy 4</strong></summary>
<br>

It checks for `~/.config/omarchy/shell.json` and the `omarchy` CLI. If you've
just installed Quattro and haven't touched the bar yet, `shell.json` may
genuinely not exist — that's fine, the installer seeds one from Omarchy's own
shipped defaults automatically. The warning is really aimed at "you still have
`~/.config/waybar` and nothing Quattro-shaped" — i.e. you're probably still on
Omarchy 3, in which case use [`../linux/`](../linux/README.md) instead.
</details>

<details>
<summary><strong>Module doesn't appear on the bar</strong></summary>
<br>

Re-run `./install.sh` — step 7 patches `shell.json` automatically. Check that
`"id": "praybar"` appears somewhere under `bar.layout` in
`~/.config/omarchy/shell.json`. If it's there but nothing renders, force a full
restart: `omarchy-restart-shell`.
</details>

<details>
<summary><strong>Text doesn't turn a different color in the final 5 minutes</strong></summary>
<br>

The module sets `"class": "urgent"` only in that window — `urgent` is the one
class name actually documented to mean something to Quattro's theme (`Color.urgent`,
the same token battery/network warnings use), so if your theme colors things on
`class: "urgent"` at all, this is where it'll show. That said, it's still the
shell's own rendering deciding whether a bar *command* module's class gets
colored the way a first-party widget's does, so treat it as a bonus rather
than the primary signal. The guaranteed cue is the icon itself: the bar swaps
to 🔔 for that same final 5 minutes regardless of any theme/coloring support.
</details>

<details>
<summary><strong>No azan sound plays</strong></summary>
<br>

Install `mpv` or `paplay`, or drop your own file at
`~/.config/omarchy/bar/scripts/azan.mp3`.
</details>

<details>
<summary><strong>Times look slightly off from my exact area</strong></summary>
<br>

Same fix as the Waybar version: set `MANUAL_LATITUDE` / `MANUAL_LONGITUDE` in
`praybar.py` for a guaranteed-exact fix, in case Wi-Fi positioning isn't
available on this machine.
</details>

---

## 🏗️ Project Structure

```
omarchy4/
├── praybar.py                    # main module script (same logic as the Waybar version)
├── install.sh                    # installer
├── uninstall.sh                  # clean removal
├── assets/
│   └── azan.mp3                  # default azan sound
├── scripts/
│   └── patch_shell_json.py       # shell.json patcher (add/remove the module)
└── systemd/
    ├── praybar-refresh.service   # daily fetch job
    └── praybar-refresh.timer     # fires at 12:00 daily
```

---

## 🔬 Design notes / what's confirmed vs. best-effort

Being upfront about what this port relies on, since Omarchy 4 shipped very
recently and some of this is inferred from the Omarchy source/docs rather
than tested against every theme:

| Piece | Status |
|---|---|
| `shell.json` custom `"type": "command"` module accepting Waybar-style JSON | **Confirmed** — documented in `docs/omarchy-shell.md`, and referenced directly in the Quattro PR's `CustomCommandModule.update()` / `parseModuleJson()` code path |
| No deep-merge once `shell.json` exists → must seed from Omarchy defaults before first patch | **Confirmed** — documented explicitly ("shell.json is canonical — there is no deep-merge") |
| `omarchy-shell shell reloadConfig` IPC re-reads `shell.json` live | **Confirmed** — documented IPC method table |
| `notify-send` keeps working unchanged (shell replaces Mako as the notification daemon) | **Reasonable inference**, not explicitly tested here — the shell is described as absorbing notifications entirely, which implies it registers as the standard freedesktop notification daemon |
| `"class": "urgent"` maps to `Color.urgent` for the final-5-minute state | **Partially confirmed** — `Color.urgent` is a documented theme token, but whether a *command* module's `class` string is wired to it the same way a first-party widget is isn't spelled out. Kept because it's the one class name with any documented meaning at all; the 🔔 icon swap is the part that's guaranteed to render regardless |

If anything above turns out wrong on your setup, the countdown **text and
tooltip themselves are unaffected** — worst case you lose the color-coded
urgency, nothing else breaks.

---

## 📜 License

Released under the [MIT License](../LICENSE) (applies to the whole `praybar`
project).

---

<div align="center">

### 🤝 Built by [Diea Abdeltwab](https://github.com/diea-abdeltwab)

*Data Engineer · Software Engineer · Turning raw data into reliable systems*

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/diea-abdeltwab/)
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/diea-abdeltwab)

![Footer](https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12&height=100&section=footer)

</div>
