package com.prayer.countdown

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import java.util.Calendar

/**
 * Schedules one exact alarm per remaining prayer today (using AlarmManager, so it fires even if
 * the app is closed / device is dozing), plus a resolved alarm for tomorrow's Fajr.
 */
object AzanScheduler {

    private const val PREFS = "azan_schedule"
    private const val KEY_TOMORROW_FAJR = "tomorrow_fajr_millis"

    fun scheduleAll(context: Context, today: DayTimings, repo: PrayerRepository) {
        val am = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val now = Calendar.getInstance()
        val fiveMin = 5L * 60 * 1000

        for (key in PrayerKey.COUNTDOWN_ORDER) {
            val cal = today.calendarFor(key, now)
            if (cal.timeInMillis > now.timeInMillis) {
                scheduleOne(context, am, key, cal.timeInMillis)
                val imminentAt = cal.timeInMillis - fiveMin
                if (imminentAt > now.timeInMillis) {
                    scheduleImminent(context, am, key, imminentAt)
                }
            }
        }

        // Resolve + cache tomorrow's Fajr so the widget can show an accurate countdown
        // right after Isha, and so we can arm the alarm for it too.
        val loc = repo.getLastKnownLocation()
        if (loc != null) {
            val tomorrowIso = java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.US)
                .format(Calendar.getInstance().apply { add(Calendar.DAY_OF_YEAR, 1) }.time)
            val tomorrow = repo.getTimingsFor(tomorrowIso, loc.lat, loc.lon, loc.countryCode)
            if (tomorrow != null) {
                val tomorrowCal = Calendar.getInstance().apply { add(Calendar.DAY_OF_YEAR, 1) }
                val fajrMillis = tomorrow.calendarFor(PrayerKey.FAJR, tomorrowCal).timeInMillis
                prefs(context).edit().putLong(KEY_TOMORROW_FAJR, fajrMillis).apply()
                scheduleOne(context, am, PrayerKey.FAJR, fajrMillis, requestCodeOffset = 100)
                scheduleImminent(context, am, PrayerKey.FAJR, fajrMillis - fiveMin, requestCodeOffset = 100)
            }
        }
    }

    fun peekTomorrowFajrMillis(context: Context): Long? {
        val v = prefs(context).getLong(KEY_TOMORROW_FAJR, -1L)
        return if (v <= 0L) null else v
    }

    // Note: no canScheduleExactAlarms() check here (that AlarmManager method is API 31+
    // and doesn't exist in the API 23 stub jar this file compiles against). It's also
    // unnecessary: with targetSdkVersion 23 in the manifest, the OS never restricts exact
    // alarms for this app regardless of the real device's Android version.
    private fun scheduleOne(
        context: Context,
        am: AlarmManager,
        key: PrayerKey,
        whenMillis: Long,
        requestCodeOffset: Int = 0
    ) {
        val intent = Intent(context, AzanAlarmReceiver::class.java).apply {
            putExtra("prayer_key", key.name)
        }
        val pi = PendingIntent.getBroadcast(
            context,
            key.ordinal + requestCodeOffset,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        try {
            am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, whenMillis, pi)
        } catch (e: SecurityException) {
            am.set(AlarmManager.RTC_WAKEUP, whenMillis, pi)
        }
    }

    /** Fires 5 minutes before a prayer so the widget flips to its "imminent" color exactly on
     *  time, instead of waiting for the next 15-minute periodic refresh. */
    private fun scheduleImminent(
        context: Context,
        am: AlarmManager,
        key: PrayerKey,
        whenMillis: Long,
        requestCodeOffset: Int = 0
    ) {
        val intent = Intent(context, ImminentRefreshReceiver::class.java)
        val pi = PendingIntent.getBroadcast(
            context,
            500 + key.ordinal + requestCodeOffset,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        try {
            am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, whenMillis, pi)
        } catch (e: SecurityException) {
            am.set(AlarmManager.RTC_WAKEUP, whenMillis, pi)
        }
    }

    private fun prefs(context: Context): SharedPreferences =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}
