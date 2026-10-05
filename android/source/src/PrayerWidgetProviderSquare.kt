package com.prayer.countdown

import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent

class PrayerWidgetProviderSquare : AppWidgetProvider() {

    override fun onUpdate(context: Context, appWidgetManager: AppWidgetManager, appWidgetIds: IntArray) {
        PrayerUpdateWorker.enqueueImmediate(context)
    }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)
        if (intent.action == WidgetRenderer.ACTION_REFRESH) {
            PrayerUpdateWorker.enqueueImmediate(context)
        }
    }

    override fun onEnabled(context: Context) {
        PrayerUpdateWorker.schedulePeriodic(context)
        PrayerUpdateWorker.enqueueImmediate(context)
    }
}
