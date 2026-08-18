package com.prayer.countdown

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build

class AzanAlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val keyName = intent.getStringExtra("prayer_key") ?: PrayerKey.FAJR.name
        val serviceIntent = Intent(context, AzanService::class.java).apply {
            putExtra("prayer_key", keyName)
        }
        // 26 == Build.VERSION_CODES.O. Context.startForegroundService() is itself an
        // API 26+ method that doesn't exist on the Context class in the API 23 stub jar
        // this file compiles against, so it's called via reflection — real O+ devices
        // (virtually all of them) still get the proper foreground-service start.
        var started = false
        if (Build.VERSION.SDK_INT >= 26) {
            try {
                val m = Context::class.java.getMethod("startForegroundService", Intent::class.java)
                m.invoke(context, serviceIntent)
                started = true
            } catch (e: Exception) {
                // fall through to plain startService below
            }
        }
        if (!started) {
            context.startService(serviceIntent)
        }

        // Immediately refresh the widget so it jumps to the *next* prayer.
        PrayerUpdateWorker.enqueueImmediate(context)
    }
}
