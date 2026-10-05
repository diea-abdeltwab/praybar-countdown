package com.prayer.countdown

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.os.IBinder
import android.os.PowerManager

class AzanService : Service() {

    private var player: MediaPlayer? = null
    private var screenOffReceiver: BroadcastReceiver? = null

    companion object {
        const val NOTIF_ID = 42
        const val ACTION_STOP = "com.prayer.countdown.ACTION_STOP_AZAN"
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelfCleanly()
            return START_NOT_STICKY
        }

        val keyName = intent?.getStringExtra("prayer_key") ?: PrayerKey.FAJR.name
        val prayer = runCatching { PrayerKey.valueOf(keyName) }.getOrDefault(PrayerKey.FAJR)

        // No notification-channel setup needed: with targetSdkVersion 23 in the manifest,
        // the OS applies legacy notification behavior on any real device, channel or not.
        startForeground(NOTIF_ID, buildNotification(prayer))
        wakeScreen()
        playAzan()
        registerScreenOffReceiver()

        return START_NOT_STICKY
    }

    /** Briefly wakes the screen so the person notices the azan started. Pressing the
     *  power button afterward still turns the screen off normally — this doesn't hold
     *  it on, it only triggers the initial wake-up. */
    @Suppress("DEPRECATION")
    private fun wakeScreen() {
        try {
            val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
            val wakeLock = pm.newWakeLock(
                PowerManager.SCREEN_BRIGHT_WAKE_LOCK or PowerManager.ACQUIRE_CAUSES_WAKEUP,
                "PrayerCountdown:AzanWake"
            )
            wakeLock.acquire(10_000L)
        } catch (e: Exception) {
            // Non-critical cosmetic feature — never let this block the azan itself.
        }
    }

    private fun playAzan() {
        stopPlayerOnly()
        player = MediaPlayer().apply {
            // USAGE_MEDIA (not USAGE_ALARM) so the azan plays on the regular media volume —
            // the person can raise/lower it with the normal volume rocker while it's playing.
            setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                    .build()
            )
            val afd = resources.openRawResourceFd(R.raw.azan)
            setDataSource(afd.fileDescriptor, afd.startOffset, afd.length)
            afd.close()
            isLooping = false
            setOnCompletionListener { stopSelfCleanly() }
            prepare()
            start()
        }
    }

    /** Stops the azan when the screen turns off — the closest reliable signal to
     *  "the person pressed the power button" available to a regular app. */
    private fun registerScreenOffReceiver() {
        if (screenOffReceiver != null) return
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                stopSelfCleanly()
            }
        }
        screenOffReceiver = receiver
        registerReceiver(receiver, IntentFilter(Intent.ACTION_SCREEN_OFF))
    }

    private fun unregisterScreenOffReceiver() {
        screenOffReceiver?.let {
            runCatching { unregisterReceiver(it) }
        }
        screenOffReceiver = null
    }

    @Suppress("DEPRECATION")
    private fun buildNotification(prayer: PrayerKey): Notification {
        val stopIntent = Intent(this, AzanService::class.java).apply { action = ACTION_STOP }
        val stopPending = PendingIntent.getService(
            this, 0, stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val res = LocaleHelper.localizedResources(this)
        val prayerName = res.getString(prayer.nameResId)
        val title = res.getString(R.string.azan_title, prayerName)

        // Plain Notification.Builder(Context) — the pre-O constructor, since this build
        // is compiled against the API 23 framework stub (no channel-based constructor
        // available there, and targetSdkVersion 23 doesn't require one at runtime either).
        return Notification.Builder(this)
            .setSmallIcon(R.drawable.ic_notification_mosque)
            .setContentTitle(title)
            .setContentText(res.getString(R.string.azan_text))
            .setPriority(Notification.PRIORITY_MAX)
            .setCategory(Notification.CATEGORY_ALARM)
            .setOngoing(true)
            .addAction(R.drawable.ic_stop, res.getString(R.string.azan_stop_action), stopPending)
            .build()
    }

    private fun stopPlayerOnly() {
        player?.let {
            runCatching { if (it.isPlaying) it.stop() }
            runCatching { it.release() }
        }
        player = null
    }

    @Suppress("DEPRECATION")
    private fun stopSelfCleanly() {
        stopPlayerOnly()
        unregisterScreenOffReceiver()
        // stopForeground(boolean) is the original signature available in the API 23 stub —
        // the STOP_FOREGROUND_REMOVE int-flag overload was added in API 24.
        stopForeground(true)
        stopSelf()
    }

    override fun onDestroy() {
        stopPlayerOnly()
        unregisterScreenOffReceiver()
        super.onDestroy()
    }
}
