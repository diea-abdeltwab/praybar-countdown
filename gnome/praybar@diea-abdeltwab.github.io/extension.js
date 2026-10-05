// praybar - prayer-time countdown for the GNOME Shell top bar (GNOME 45+, ESM).
//
// Responsibilities are split on purpose:
//   backend/praybar_backend.py  location + Aladhan fetch + caching  (slow, networked)
//   prayerLogic.js              next prayer, countdown, formatting  (pure, unit-tested)
//   extension.js (this file)    UI, timers, notification, azan      (shell glue)

import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import * as Logic from './prayerLogic.js';

const TICK_SECONDS = 15;       // UI/notification cadence; far below the 60 s notify window
const RETRY_SECONDS = 60;      // after a failed backend call
const REFRESH_SECONDS = 3600;  // normal backend cadence (it is cache-backed, so cheap)
const BLINK_MS = 700;

// 'center' index 0 = immediately left of the clock, like the Waybar versions.
const POSITIONS = {left: [1, 'left'], center: [0, 'center'], right: [0, 'right']};

// ─── Small promise wrappers around Gio async APIs ────────────────────────────

function communicate(proc, cancellable) {
    return new Promise((resolve, reject) => {
        proc.communicate_utf8_async(null, cancellable, (p, res) => {
            try {
                // GJS returns [ok, stdout, stderr]; pick the first string so we
                // do not depend on whether the leading boolean is included.
                const out = p.communicate_utf8_finish(res).find(v => typeof v === 'string');
                resolve(out ?? '');
            } catch (e) {
                reject(e);
            }
        });
    });
}

function waitFor(proc, cancellable) {
    return new Promise((resolve, reject) => {
        proc.wait_async(cancellable, (p, res) => {
            try {
                p.wait_finish(res);
                resolve();
            } catch (e) {
                reject(e);
            }
        });
    });
}

// ─── View: the top-bar button and its dropdown ───────────────────────────────

const PraybarIndicator = GObject.registerClass(
class PraybarIndicator extends PanelMenu.Button {
    _init({onRefresh, onStopAzan, onSettings}) {
        super._init(0.0, 'praybar', false);
        this._blinkId = 0;
        this._dim = false;

        this._label = new St.Label({
            text: '🕌 …',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'praybar-label',
        });
        this.add_child(this._label);

        this._header = new PopupMenu.PopupMenuItem('🕌 Prayer Times', {reactive: false, can_focus: false});
        this.menu.addMenuItem(this._header);

        this._status = new PopupMenu.PopupMenuItem('', {reactive: false, can_focus: false});
        this._status.visible = false;
        this.menu.addMenuItem(this._status);

        this._rows = new PopupMenu.PopupMenuSection();
        this.menu.addMenuItem(this._rows);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        this._stopItem = new PopupMenu.PopupMenuItem('Stop azan');
        this._stopItem.connect('activate', onStopAzan);
        this._stopItem.visible = false;
        this.menu.addMenuItem(this._stopItem);

        const refresh = new PopupMenu.PopupMenuItem('Refresh now');
        refresh.connect('activate', onRefresh);
        this.menu.addMenuItem(refresh);

        const settings = new PopupMenu.PopupMenuItem('Settings');
        settings.connect('activate', onSettings);
        this.menu.addMenuItem(settings);
    }

    setLabel(text, level) {
        this._label.set_text(text);
        for (const l of ['near', 'soon'])
            this._label.remove_style_class_name(`praybar-${l}`);
        if (level !== 'normal')
            this._label.add_style_class_name(`praybar-${level}`);
        this._setBlink(level === 'soon');
    }

    setSchedule(title, rows, statusText) {
        this._header.label.set_text(title);
        this._status.label.set_text(statusText ?? '');
        this._status.visible = !!statusText;

        this._rows.removeAll();
        for (const row of rows) {
            const item = new PopupMenu.PopupBaseMenuItem({reactive: false, can_focus: false});
            const name = new St.Label({text: row.name, x_expand: true});
            const time = new St.Label({text: row.time});
            if (row.isNext) {
                name.add_style_class_name('praybar-next');
                time.add_style_class_name('praybar-next');
            }
            item.add_child(name);
            item.add_child(time);
            this._rows.addMenuItem(item);
        }
    }

    setStopVisible(visible) {
        this._stopItem.visible = visible;
    }

    // Timer-based (not Clutter transitions) on purpose: with animations
    // disabled an ease() completes instantly, and a self-re-arming
    // onComplete would spin the shell. A GLib timeout cannot do that.
    _setBlink(on) {
        if (on && !St.Settings.get().enable_animations)
            on = false;  // respect "reduce motion"
        if (on && !this._blinkId) {
            this._blinkId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, BLINK_MS, () => {
                this._dim = !this._dim;
                this._label.opacity = this._dim ? 110 : 255;
                return GLib.SOURCE_CONTINUE;
            });
        } else if (!on && this._blinkId) {
            GLib.Source.remove(this._blinkId);
            this._blinkId = 0;
            this._dim = false;
            this._label.opacity = 255;
        }
    }

    stop() {
        this._setBlink(false);
    }
});

// ─── Controller ──────────────────────────────────────────────────────────────

export default class PraybarExtension extends Extension {
    enable() {
        this._settings = this.getSettings();
        this._cancellable = new Gio.Cancellable();
        this._payload = null;
        this._error = null;
        this._refreshing = false;
        this._refreshAgain = false;
        this._nextAttempt = 0;
        this._renderKey = null;
        this._azanProc = null;
        this._procs = new Set();
        this._sources = new Set();
        this._signals = [];

        this._createIndicator();

        const watch = (keys, fn) => {
            for (const key of keys)
                this._signals.push(this._settings.connect(`changed::${key}`, fn));
        };
        watch(['calc-method'], () => this._scheduleRefresh());
        watch(['time-format', 'prayer-names'], () => {
            this._renderKey = null;
            this._tick();
        });
        watch(['panel-position'], () => {
            this._destroyIndicator();
            this._createIndicator();
            this._tick();
        });

        this._addSource(GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, TICK_SECONDS, () => {
            this._tick();
            return GLib.SOURCE_CONTINUE;
        }));

        this._refresh();
    }

    disable() {
        this._cancellable?.cancel();
        for (const id of this._signals)
            this._settings.disconnect(id);
        this._signals = [];
        for (const id of this._sources)
            GLib.Source.remove(id);
        this._sources.clear();

        this._stopAzan();
        for (const proc of this._procs)
            proc.force_exit();
        this._procs.clear();

        this._destroyIndicator();
        this._cancellable = null;
        this._payload = null;
        this._settings = null;  // doubles as the "disabled" flag for in-flight async work
    }

    // ── indicator lifecycle ──

    _createIndicator() {
        this._indicator = new PraybarIndicator({
            onRefresh: () => this._refresh(),
            onStopAzan: () => this._stopAzan(),
            onSettings: () => this.openPreferences(),
        });
        const [index, box] = POSITIONS[this._settings.get_string('panel-position')] ?? POSITIONS.center;
        Main.panel.addToStatusArea(this.uuid, this._indicator, index, box);
        this._renderKey = null;
    }

    _destroyIndicator() {
        if (!this._indicator)
            return;
        this._indicator.stop();
        this._indicator.destroy();
        this._indicator = null;
    }

    _addSource(id) {
        this._sources.add(id);
        return id;
    }

    // ── backend ──

    _scheduleRefresh() {
        // Debounce: dragging a spin button fires many changed:: signals.
        if (this._debounceId) {
            GLib.Source.remove(this._debounceId);
            this._sources.delete(this._debounceId);  // else disable() would remove it twice
        }
        this._debounceId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 800, () => {
            this._sources.delete(this._debounceId);
            this._debounceId = 0;
            this._refresh();
            return GLib.SOURCE_REMOVE;
        });
        this._addSource(this._debounceId);
    }

    async _refresh() {
        if (this._refreshing) {
            this._refreshAgain = true;
            return;
        }
        this._refreshing = true;
        try {
            const result = await this._runBackend();
            if (!this._settings)
                return;
            if (result.ok) {
                this._payload = result;
                this._error = null;
            } else {
                this._error = result.error ?? 'Unknown backend error';
            }
        } catch (e) {
            if (!this._settings)
                return;
            this._error = e.message;
        } finally {
            this._refreshing = false;
        }

        // Next call: soon after a failure, otherwise hourly - but never later
        // than just after local midnight, so the new day's times load promptly.
        const now = new Date();
        const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 0, 0, 5).getTime();
        this._nextAttempt = this._error
            ? Date.now() + RETRY_SECONDS * 1000
            : Math.min(Date.now() + REFRESH_SECONDS * 1000, midnight);

        this._renderKey = null;
        this._tick();

        if (this._refreshAgain) {
            this._refreshAgain = false;
            this._refresh();
        }
    }

    async _runBackend() {
        const s = this._settings;
        const argv = [
            'python3',
            GLib.build_filenamev([this.path, 'backend', 'praybar_backend.py']),
            '--method', String(s.get_int('calc-method')),
        ];
        const proc = new Gio.Subprocess({
            argv,
            flags: Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE,
        });
        proc.init(this._cancellable);
        this._procs.add(proc);
        try {
            const stdout = await communicate(proc, this._cancellable);
            try {
                return JSON.parse(stdout);
            } catch {
                throw new Error('Backend returned invalid output (is python3 installed?)');
            }
        } finally {
            this._procs.delete(proc);
        }
    }

    // ── per-tick work: refresh scheduling, notification gate, rendering ──

    // Next to the clock the text is followed by " --", like the Waybar
    // versions ("Maghrib 25m  --  Tuesday 19:08"). Elsewhere it is omitted.
    _setBar(text, level) {
        const sep = this._settings.get_string('panel-position') === 'center' ? '  --' : '';
        this._indicator.setLabel(`${text}${sep}`, level);
    }

    _tick() {
        if (!this._indicator || !this._settings)
            return;

        if (!this._refreshing && Date.now() >= this._nextAttempt)
            this._refresh();

        if (!this._payload) {
            this._setBar(this._error ? '🕌 –' : '🕌 …', 'normal');
            this._indicator.setSchedule('🕌 Prayer Times', [],
                this._error ? `Could not fetch prayer times: ${this._error}` : 'Loading…');
            return;
        }

        const now = new Date();
        const payload = this._payload;
        const next = Logic.nextPrayer(payload, now);
        const secs = (next.at - now) / 1000;

        const started = Logic.justStarted(payload, now);
        if (started && started.id !== this._settings.get_string('last-notified')) {
            // Persisted in GSettings, so reloading the extension or the shell
            // inside the window cannot fire the same prayer twice.
            this._settings.set_string('last-notified', started.id);
            this._onPrayerTime(started.key);
        }

        const lang = this._settings.get_string('prayer-names');
        const names = Logic.NAMES[lang] ?? Logic.NAMES.en;

        if (secs <= 0) {
            // Cached data is more than a day old and we are offline.
            this._setBar('🕌 –', 'normal');
        } else {
            this._setBar(
                `🕌 ${names[next.key]} ${Logic.formatCountdown(next.at - now)}`,
                Logic.urgency(secs));
        }

        // The dropdown only changes when the day, next prayer, or a setting does.
        const format = this._settings.get_string('time-format');
        const renderKey = [payload.date, next.key, format, lang, payload.city, payload.stale, this._error].join('|');
        if (renderKey === this._renderKey)
            return;
        this._renderKey = renderKey;

        const rows = Logic.SCHEDULE_KEYS.map(key => ({
            name: names[key],
            time: Logic.formatClock(payload.timings[key], format),
            isNext: key === next.key,
        }));
        let status = null;
        if (payload.stale)
            status = '⚠ Offline - showing the last cached times';
        else if (this._error)
            status = `⚠ Refresh failed: ${this._error}`;
        this._indicator.setSchedule(`🕌 Prayer Times - ${payload.city}`, rows, status);
    }

    // ── prayer time reached ──

    _onPrayerTime(key) {
        const s = this._settings;
        const lang = s.get_string('prayer-names');
        const name = (Logic.NAMES[lang] ?? Logic.NAMES.en)[key];

        if (s.get_boolean('azan-enabled'))
            this._playAzan();
        if (s.get_boolean('notifications-enabled'))
            this._notify(`🕌 ${name}`, 'الله أكبر — Allahu Akbar', this._azanProc);
    }

    _playAzan() {
        this._stopAzan();
        const file = GLib.build_filenamev([this.path, 'assets', 'azan.mp3']);
        const players = [
            ['mpv', '--no-terminal', '--no-video', '--no-audio-display', '--vo=null', '--af=lavfi=[adelay=800|800]', file],
            ['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet', file],
            ['paplay', file],
            ['pw-play', file],
        ];
        for (const argv of players) {
            if (!GLib.find_program_in_path(argv[0]))
                continue;
            try {
                const proc = Gio.Subprocess.new(
                    argv, Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE);
                this._azanProc = proc;
                this._indicator?.setStopVisible(true);
                waitFor(proc, null).catch(() => {}).then(() => {
                    // Only clear state if this is still the active player.
                    if (this._azanProc === proc) {
                        this._azanProc = null;
                        this._indicator?.setStopVisible(false);
                    }
                });
                return;
            } catch {
                continue;
            }
        }
        console.warn('praybar: no audio player found (install mpv, ffmpeg or pulseaudio-utils)');
    }

    _stopAzan() {
        const proc = this._azanProc;
        this._azanProc = null;
        this._indicator?.setStopVisible(false);
        proc?.force_exit();
    }

    // Persistent notification with a "Stop azan" button. Done through
    // notify-send (a freedesktop notification) instead of the shell's
    // MessageTray classes, whose constructors changed between GNOME 45 and 46+;
    // this keeps one code path across every supported version.
    async _notify(title, body, azanProc) {
        if (!GLib.find_program_in_path('notify-send')) {
            Main.notify(title, body);
            return;
        }
        let proc;
        try {
            proc = new Gio.Subprocess({
                argv: ['notify-send', '--app-name=praybar', '--urgency=critical', '--wait',
                    '--action=stop=Stop azan', title, body],
                flags: Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE,
            });
            proc.init(null);
        } catch {
            Main.notify(title, body);
            return;
        }
        this._procs.add(proc);
        try {
            // Returns when the notification is dismissed OR its button is pressed.
            await waitFor(proc, this._cancellable);
        } catch {
            return;  // cancelled because the extension was disabled
        } finally {
            this._procs.delete(proc);
        }
        // Stop only the azan THIS notification started, never a later prayer's.
        if (this._settings && azanProc && this._azanProc === azanProc)
            this._stopAzan();
    }
}
