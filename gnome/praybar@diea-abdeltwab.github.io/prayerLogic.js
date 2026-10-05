// Pure logic only: no `gi://` or shell imports, so it can be unit-tested with
// plain node (see ../tests/prayerLogic.test.mjs). All UI/IO lives in extension.js.

export const PRAYER_KEYS = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha'];
export const SCHEDULE_KEYS = ['Fajr', 'Sunrise', 'Dhuhr', 'Asr', 'Maghrib', 'Isha'];

export const NAMES = {
    en: {Fajr: 'Fajr', Sunrise: 'Sunrise', Dhuhr: 'Dhuhr', Asr: 'Asr', Maghrib: 'Maghrib', Isha: 'Isha'},
    ar: {Fajr: 'الفجر', Sunrise: 'الشروق', Dhuhr: 'الظهر', Asr: 'العصر', Maghrib: 'المغرب', Isha: 'العشاء'},
};

export const NEAR_SECS = 15 * 60;  // text turns amber
export const SOON_SECS = 5 * 60;   // text turns red and blinks
export const NOTIFY_WINDOW_SECS = 60;

const pad2 = n => String(n).padStart(2, '0');

export function isoDate(d) {
    return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

// Build a local Date for "HH:MM" on `isoDay` (+ dayOffset). The API returns
// local wall-clock times, so they are interpreted in the system time zone.
function dayAt(isoDay, hhmm, dayOffset = 0) {
    const [y, m, d] = isoDay.split('-').map(Number);
    const [hh, mm] = hhmm.slice(0, 5).split(':').map(Number);
    return new Date(y, m - 1, d + dayOffset, hh, mm, 0, 0);
}

// Next of the five prayers after `now`. Uses payload.date (not `now`) as the
// base day, so right after midnight - before the refresh lands - it still
// resolves to today's Fajr via payload.tomorrow_fajr.
export function nextPrayer(payload, now) {
    for (const key of PRAYER_KEYS) {
        const at = dayAt(payload.date, payload.timings[key]);
        if (at > now)
            return {key, at};
    }
    const fajr = payload.tomorrow_fajr ?? payload.timings.Fajr;
    return {key: 'Fajr', at: dayAt(payload.date, fajr, 1)};
}

// The prayer that started within the last `windowSecs`, or null. The id is
// derived from the prayer's own date, so the same prayer always has the same
// id however many times (or from which payload) it is evaluated.
export function justStarted(payload, now, windowSecs = NOTIFY_WINDOW_SECS) {
    const candidates = PRAYER_KEYS.map(key => ({key, at: dayAt(payload.date, payload.timings[key])}));
    if (payload.tomorrow_fajr)
        candidates.push({key: 'Fajr', at: dayAt(payload.date, payload.tomorrow_fajr, 1)});

    for (const {key, at} of candidates) {
        const elapsed = (now - at) / 1000;
        if (elapsed >= 0 && elapsed <= windowSecs)
            return {key, at, id: `${isoDate(at)}-${key}`};
    }
    return null;
}

export function formatCountdown(ms) {
    const total = Math.max(0, Math.floor(ms / 1000));
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    return h ? `${h}:${pad2(m)}` : `${m}m`;
}

export function formatClock(hhmm, format) {
    const [hh, mm] = hhmm.slice(0, 5).split(':').map(Number);
    if (format === '12h')
        return `${hh % 12 || 12}:${pad2(mm)} ${hh < 12 ? 'AM' : 'PM'}`;
    return `${pad2(hh)}:${pad2(mm)}`;
}

export function urgency(secs) {
    if (secs < SOON_SECS) return 'soon';
    if (secs < NEAR_SECS) return 'near';
    return 'normal';
}
