import test from 'node:test';
import assert from 'node:assert/strict';
import * as L from '../praybar@diea-abdeltwab.github.io/prayerLogic.js';

const payload = {
    date: '2026-10-04',
    timings: {Fajr: '04:54', Sunrise: '06:27', Dhuhr: '13:01', Asr: '16:36', Maghrib: '19:34', Isha: '20:56'},
    tomorrow_fajr: '04:55',
};
const at = (h, m, s = 0, day = 4) => new Date(2026, 9, day, h, m, s);

test('next prayer mid-day is Asr', () => {
    const n = L.nextPrayer(payload, at(14, 0));
    assert.equal(n.key, 'Asr');
    assert.equal(n.at.getHours(), 16);
});

test('after Isha the next prayer is tomorrow Fajr using tomorrow_fajr', () => {
    const n = L.nextPrayer(payload, at(22, 0));
    assert.equal(n.key, 'Fajr');
    assert.equal(n.at.getDate(), 5);
    assert.equal(n.at.getMinutes(), 55);
});

test('falls back to today Fajr when tomorrow_fajr is missing', () => {
    const n = L.nextPrayer({...payload, tomorrow_fajr: null}, at(22, 0));
    assert.equal(n.at.getMinutes(), 54);
});

test('just after midnight with yesterday payload still points at today Fajr', () => {
    const n = L.nextPrayer(payload, new Date(2026, 9, 5, 0, 0, 3));
    assert.equal(n.key, 'Fajr');
    assert.equal(n.at.getDate(), 5);
});

test('justStarted fires inside the window only', () => {
    assert.equal(L.justStarted(payload, at(19, 34, 0)).key, 'Maghrib');
    assert.equal(L.justStarted(payload, at(19, 34, 45)).key, 'Maghrib');
    assert.equal(L.justStarted(payload, at(19, 33, 59)), null);
    assert.equal(L.justStarted(payload, at(19, 35, 1)), null);
});

test('Sunrise never triggers', () => {
    assert.equal(L.justStarted(payload, at(6, 27, 10)), null);
});

test('id is stable and date-based; stale payload still fires tomorrow Fajr', () => {
    const a = L.justStarted(payload, at(19, 34, 5));
    const b = L.justStarted(payload, at(19, 34, 50));
    assert.equal(a.id, b.id);
    assert.equal(a.id, '2026-10-04-Maghrib');
    const f = L.justStarted(payload, new Date(2026, 9, 5, 4, 55, 20));
    assert.equal(f.id, '2026-10-05-Fajr');
});

test('formatCountdown', () => {
    assert.equal(L.formatCountdown(0), '0m');
    assert.equal(L.formatCountdown(-5000), '0m');
    assert.equal(L.formatCountdown(59 * 60e3 + 59e3), '59m');
    assert.equal(L.formatCountdown(3600e3), '1:00');
    assert.equal(L.formatCountdown(125 * 60e3), '2:05');
});

test('formatClock', () => {
    assert.equal(L.formatClock('13:05', '24h'), '13:05');
    assert.equal(L.formatClock('13:05', '12h'), '1:05 PM');
    assert.equal(L.formatClock('00:07', '12h'), '12:07 AM');
    assert.equal(L.formatClock('12:00 (EET)', '12h'), '12:00 PM');
});

test('urgency thresholds', () => {
    assert.equal(L.urgency(100), 'soon');
    assert.equal(L.urgency(299), 'soon');
    assert.equal(L.urgency(300), 'near');
    assert.equal(L.urgency(899), 'near');
    assert.equal(L.urgency(900), 'normal');
});
