package com.prayer.countdown

import android.content.Context

/**
 * Stores whether prayer times are displayed in 12-hour (with AM/PM) or 24-hour
 * format. Only affects display — all internal storage/parsing (DayTimings,
 * calendarFor, etc.) always stays in 24-hour "HH:mm", exactly as returned by the
 * API. This mirrors the pattern used by LocaleHelper for the language toggle.
 */
object TimeFormatHelper {

    private const val PREFS = "app_settings"
    private const val KEY_FORMAT = "time_format" // "24" or "12"

    fun is24Hour(context: Context): Boolean {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return prefs.getString(KEY_FORMAT, "24") == "24"
    }

    fun toggle(context: Context) {
        val next = if (is24Hour(context)) "12" else "24"
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(KEY_FORMAT, next).apply()
    }

    /**
     * Formats a "HH:mm" 24-hour time string (as stored on DayTimings) for display,
     * according to the saved preference. In 12-hour mode, appends a localized
     * AM/PM marker (English "AM"/"PM", Arabic "ص"/"م").
     */
    fun format(context: Context, time24: String): String {
        val parts = time24.split(":")
        if (parts.size != 2) return time24
        val h = parts[0].toIntOrNull() ?: return time24
        val m = parts[1].toIntOrNull() ?: return time24

        if (is24Hour(context)) {
            return String.format("%02d:%02d", h, m)
        }

        val isPm = h >= 12
        var h12 = h % 12
        if (h12 == 0) h12 = 12
        val isRtl = LocaleHelper.isRtl(context)
        val marker = if (isRtl) {
            if (isPm) "م" else "ص"
        } else {
            if (isPm) "PM" else "AM"
        }
        return String.format("%d:%02d %s", h12, m, marker)
    }

    /** Button label showing the format the user would switch TO, e.g. lang toggle. */
    fun toggleLabel(context: Context): String {
        val isRtl = LocaleHelper.isRtl(context)
        return if (is24Hour(context)) {
            if (isRtl) "١٢ ساعة" else "12h"
        } else {
            if (isRtl) "٢٤ ساعة" else "24h"
        }
    }
}
