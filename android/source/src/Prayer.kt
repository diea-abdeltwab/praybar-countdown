package com.prayer.countdown

import java.util.Calendar

enum class PrayerKey(val nameResId: Int) {
    FAJR(R.string.prayer_fajr),
    SHUROUQ(R.string.prayer_shurouq),
    DHUHR(R.string.prayer_dhuhr),
    ASR(R.string.prayer_asr),
    MAGHRIB(R.string.prayer_maghrib),
    ISHA(R.string.prayer_isha);

    companion object {
        val COUNTDOWN_ORDER = listOf(FAJR, DHUHR, ASR, MAGHRIB, ISHA)
    }
}

data class DayTimings(
    val fajr: String,
    val shurouq: String,
    val dhuhr: String,
    val asr: String,
    val maghrib: String,
    val isha: String,
    val dateIso: String,
    val hijriDate: String,
    val cityName: String
) {
    fun timeFor(key: PrayerKey): String = when (key) {
        PrayerKey.FAJR -> fajr
        PrayerKey.SHUROUQ -> shurouq
        PrayerKey.DHUHR -> dhuhr
        PrayerKey.ASR -> asr
        PrayerKey.MAGHRIB -> maghrib
        PrayerKey.ISHA -> isha
    }

    fun calendarFor(key: PrayerKey, base: Calendar): Calendar {
        val parts = timeFor(key).split(":")
        val h = parts[0].toInt()
        val m = parts[1].toInt()
        val cal = base.clone() as Calendar
        cal.set(Calendar.HOUR_OF_DAY, h)
        cal.set(Calendar.MINUTE, m)
        cal.set(Calendar.SECOND, 0)
        cal.set(Calendar.MILLISECOND, 0)
        return cal
    }
}

data class NextPrayer(val key: PrayerKey, val whenMillis: Long)
