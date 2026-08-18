package com.prayer.countdown

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class ImminentRefreshReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        PrayerUpdateWorker.enqueueImmediate(context)
    }
}
