package com.prayer.countdown

import java.util.Calendar
import java.util.concurrent.TimeUnit

object PrayerLogic {

    /**
     * Finds the next upcoming prayer given today's timings.
     * If everything today has passed, [tomorrowFajr] (already resolved) is used.
     */
    fun findNext(today: DayTimings, tomorrowFajrMillis: Long?): NextPrayer {
        val now = Calendar.getInstance()
        for (key in PrayerKey.COUNTDOWN_ORDER) {
            val cal = today.calendarFor(key, now)
            if (cal.timeInMillis > now.timeInMillis) {
                return NextPrayer(key, cal.timeInMillis)
            }
        }
        // Everything passed today — fall back to tomorrow's Fajr if we have it,
        // otherwise estimate using today's Fajr + 24h (fixed up on next real fetch).
        val fallback = tomorrowFajrMillis
            ?: (today.calendarFor(PrayerKey.FAJR, now).timeInMillis + TimeUnit.DAYS.toMillis(1))
        return NextPrayer(PrayerKey.FAJR, fallback)
    }

    /** "2:15:30" or "45:12" style countdown, Arabic-Indic digits kept off for widget clarity. */
    fun formatCountdown(remainingMillis: Long): String {
        val total = maxOf(0L, remainingMillis / 1000)
        val h = total / 3600
        val m = (total % 3600) / 60
        val s = total % 60
        return if (h > 0) String.format("%d:%02d:%02d", h, m, s)
        else String.format("%02d:%02d", m, s)
    }

    /** Short label like "متبقي" state used to tint the widget when a prayer is close. */
    fun isImminent(remainingMillis: Long): Boolean = remainingMillis in 0..(5 * 60 * 1000)
}
