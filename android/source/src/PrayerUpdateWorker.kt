package com.prayer.countdown

import android.app.AlarmManager
import android.app.IntentService
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.SystemClock

/**
 * Plain-framework replacement for WorkManager (WorkManager needs AndroidX/Maven, which
 * isn't reachable in this build). Keeps the exact same public API (enqueueImmediate /
 * schedulePeriodic) so every call site elsewhere in the app is unchanged.
 *
 * - enqueueImmediate: starts an IntentService, which already runs its work off the main
 *   thread by design — the direct equivalent of a one-off WorkManager job.
 * - schedulePeriodic: arms a repeating AlarmManager alarm targeting that same service,
 *   since AlarmManager keeps firing even if the app process isn't currently running.
 */
object PrayerUpdateWorker {

    private const val REQUEST_CODE_PERIODIC = 900
    private const val PERIOD_MILLIS = 15L * 60 * 1000 // 15 minutes

    fun enqueueImmediate(context: Context) {
        context.startService(Intent(context, PrayerUpdateIntentService::class.java))
    }

    fun schedulePeriodic(context: Context) {
        val am = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val intent = Intent(context, PrayerUpdateIntentService::class.java)
        val pi = PendingIntent.getService(
            context, REQUEST_CODE_PERIODIC, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        am.setInexactRepeating(
            AlarmManager.ELAPSED_REALTIME,
            SystemClock.elapsedRealtime() + PERIOD_MILLIS,
            PERIOD_MILLIS,
            pi
        )
    }
}

/** Does the actual fetch + alarm rescheduling + widget re-render, off the main thread
 *  (IntentService runs onHandleIntent on its own worker thread automatically). */
class PrayerUpdateIntentService : IntentService("PrayerUpdateIntentService") {
    override fun onHandleIntent(intent: Intent?) {
        val repo = PrayerRepository(this)
        val today = repo.getTodayTimings()
        if (today != null) {
            AzanScheduler.scheduleAll(this, today, repo)
        }
        WidgetRenderer.updateAllSizes(this)
    }
}
