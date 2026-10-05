import Adw from 'gi://Adw';
import Gio from 'gi://Gio';
import Gtk from 'gi://Gtk';

import {ExtensionPreferences} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

// Aladhan calculation methods. https://aladhan.com/calculation-methods
const METHODS = [
    [5, 'Egyptian General Authority of Survey'],
    [3, 'Muslim World League'],
    [4, 'Umm Al-Qura (Mecca)'],
    [2, 'ISNA (North America)'],
    [1, 'University of Islamic Sciences, Karachi'],
    [8, 'Gulf Region'],
    [9, 'Kuwait'],
    [10, 'Qatar'],
    [11, 'Singapore'],
    [12, 'France (UOIF)'],
    [13, 'Turkey (Diyanet)'],
];

// Bind an Adw.ComboRow to a GSettings key through a [value, label] table.
function addCombo(group, settings, {key, title, subtitle = '', options, type}) {
    const row = new Adw.ComboRow({
        title,
        subtitle,
        model: Gtk.StringList.new(options.map(([, label]) => label)),
    });
    const read = () => settings.get_value(key).deepUnpack();
    const sync = () => {
        const index = options.findIndex(([value]) => value === read());
        if (index >= 0 && row.selected !== index)
            row.selected = index;
    };
    sync();
    row.connect('notify::selected', () => {
        const [value] = options[row.selected];
        if (value === read())
            return;
        if (type === 'i')
            settings.set_int(key, value);
        else
            settings.set_string(key, value);
    });
    settings.connect(`changed::${key}`, sync);
    group.add(row);
    return row;
}

function addSwitch(group, settings, key, title, subtitle = '') {
    const row = new Adw.SwitchRow({title, subtitle});
    settings.bind(key, row, 'active', Gio.SettingsBindFlags.DEFAULT);
    group.add(row);
    return row;
}

export default class PraybarPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const settings = this.getSettings();
        const page = new Adw.PreferencesPage({
            title: 'praybar',
            icon_name: 'preferences-system-time-symbolic',
        });
        window.add(page);

        // ── Display ──
        const display = new Adw.PreferencesGroup({title: 'Display'});
        page.add(display);
        addCombo(display, settings, {
            key: 'time-format', type: 's', title: 'Clock format',
            options: [['24h', '24-hour (13:05)'], ['12h', '12-hour (1:05 PM)']],
        });
        addCombo(display, settings, {
            key: 'prayer-names', type: 's', title: 'Prayer names',
            options: [['en', 'English'], ['ar', 'العربية']],
        });
        addCombo(display, settings, {
            key: 'panel-position', type: 's', title: 'Position in the top bar',
            options: [['center', 'Next to the clock'], ['right', 'Right'], ['left', 'Left']],
        });

        // ── Calculation ──
        const calc = new Adw.PreferencesGroup({title: 'Calculation'});
        page.add(calc);
        addCombo(calc, settings, {
            key: 'calc-method', type: 'i', title: 'Calculation method',
            subtitle: 'Which authority defines the Fajr/Isha angles',
            options: METHODS,
        });
        calc.set_description('Your location is detected automatically and refreshed every night at 00:00.');

        // ── Alerts ──
        const alerts = new Adw.PreferencesGroup({title: 'Alerts'});
        page.add(alerts);
        addSwitch(alerts, settings, 'notifications-enabled', 'Notification',
            'Persistent notification with a "Stop azan" button');
        addSwitch(alerts, settings, 'azan-enabled', 'Play the azan',
            'Needs mpv, ffmpeg (ffplay) or pulseaudio-utils (paplay)');
    }
}
