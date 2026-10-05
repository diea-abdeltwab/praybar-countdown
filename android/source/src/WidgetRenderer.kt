package com.prayer.countdown

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.SystemClock
import android.view.View
import android.widget.RemoteViews

/** Builds and pushes RemoteViews for a given widget provider + layout, shared by both widget sizes. */
object WidgetRenderer {

    const val ACTION_REFRESH = "com.prayer.countdown.ACTION_REFRESH"

    fun updateAll(context: Context, providerClass: Class<*>, layoutRes: Int, compact: Boolean) {
        val mgr = AppWidgetManager.getInstance(context)
        val ids = mgr.getAppWidgetIds(ComponentName(context, providerClass))
        if (ids.isEmpty()) return
        val views = buildViews(context, providerClass, layoutRes, compact)
        mgr.updateAppWidget(ids, views)
    }

    private fun buildViews(context: Context, providerClass: Class<*>, layoutRes: Int, compact: Boolean): RemoteViews {
        val views = RemoteViews(context.packageName, layoutRes)
        val res = LocaleHelper.localizedResources(context)
        val repo = PrayerRepository(context)
        val today = repo.getTodayTimings()

        if (today == null) {
            views.setTextViewText(R.id.tv_prayer_name, "🌙 " + res.getString(R.string.connection_error))
            if (!compact) views.setTextViewText(R.id.tv_city, res.getString(R.string.check_internet))
            views.setViewVisibility(R.id.chronometer, View.GONE)
            views.setViewVisibility(R.id.tv_static_countdown, View.VISIBLE)
            views.setTextViewText(R.id.tv_static_countdown, "—:—")
            attachRefreshClick(context, providerClass, views)
            return views
        }

        val tomorrowFajrMillis = AzanScheduler.peekTomorrowFajrMillis(context)
        val next = PrayerLogic.findNext(today, tomorrowFajrMillis)
        val nowMillis = System.currentTimeMillis()
        val remaining = (next.whenMillis - nowMillis).coerceAtLeast(0)

        views.setTextViewText(R.id.tv_prayer_name, "🕌 " + res.getString(next.key.nameResId))

        if (!compact) {
            val cityLine = if (today.cityName.isNotBlank()) today.cityName else ""
            val hijriLine = if (today.hijriDate.isNotBlank()) today.hijriDate else ""
            views.setTextViewText(
                R.id.tv_city,
                listOf(cityLine, hijriLine).filter { it.isNotBlank() }.joinToString(" · ")
            )
        }

        val base = SystemClock.elapsedRealtime() + remaining
        views.setChronometer(R.id.chronometer, base, null, true)
        setChronometerCountDownCompat(views, R.id.chronometer, true)
        views.setViewVisibility(R.id.chronometer, View.VISIBLE)
        views.setViewVisibility(R.id.tv_static_countdown, View.GONE)

        val bg = if (PrayerLogic.isImminent(remaining)) R.drawable.widget_bg_imminent else R.drawable.widget_bg_normal
        views.setInt(R.id.widget_root, "setBackgroundResource", bg)

        attachRefreshClick(context, providerClass, views)
        return views
    }

    /**
     * RemoteViews.setChronometerCountDown(int, boolean) was added in API 24, so it doesn't
     * exist in the API 23 stub jar this file is compiled against — even though the real
     * device it runs on is virtually guaranteed to have it. Call it via reflection instead,
     * guarded in a try/catch so an older device just falls back to counting up.
     */
    private fun setChronometerCountDownCompat(views: RemoteViews, viewId: Int, countDown: Boolean) {
        try {
            val m = RemoteViews::class.java.getMethod(
                "setChronometerCountDown",
                Int::class.javaPrimitiveType, Boolean::class.javaPrimitiveType
            )
            m.invoke(views, viewId, countDown)
        } catch (e: Exception) {
            // Older device without this method — chronometer just counts up instead.
        }
    }

    private fun attachRefreshClick(context: Context, providerClass: Class<*>, views: RemoteViews) {
        val intent = Intent(context, providerClass).apply {
            action = ACTION_REFRESH
        }
        val pi = PendingIntent.getBroadcast(
            context, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        views.setOnClickPendingIntent(R.id.widget_root, pi)
    }

    /** Called whenever ANY widget size needs a fresh render (both are kept in sync). */
    fun updateAllSizes(context: Context) {
        updateAll(context, PrayerWidgetProviderLarge::class.java, R.layout.widget_prayer, false)
        updateAll(context, PrayerWidgetProviderSquare::class.java, R.layout.widget_prayer_square, true)
        updateAll(context, PrayerWidgetProviderSmall::class.java, R.layout.widget_prayer_small, true)
    }
}
