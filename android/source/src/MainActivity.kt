package com.prayer.countdown

import android.app.Activity
import android.content.Context
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView

class MainActivity : Activity() {

    // Cached from the last successful load, so toggling the 12h/24h format can
    // just re-render the table instantly instead of re-fetching from the network.
    private var cachedToday: DayTimings? = null
    private var cachedNextKey: PrayerKey? = null

    private val mainHandler = Handler(Looper.getMainLooper())

    override fun attachBaseContext(newBase: Context) {
        super.attachBaseContext(LocaleHelper.localizedContext(newBase))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // Note: with targetSdkVersion 23 in the manifest, the OS applies legacy runtime
        // behavior — no POST_NOTIFICATIONS prompt and no SCHEDULE_EXACT_ALARM restriction
        // are enforced, so no runtime-permission dance is needed here at all.

        applyStaticStrings()

        (findViewById(R.id.btn_lang_toggle) as TextView).setOnClickListener {
            LocaleHelper.setLanguage(this, LocaleHelper.otherLanguage(this))
            recreate()
        }

        (findViewById(R.id.btn_format_toggle) as TextView).setOnClickListener {
            TimeFormatHelper.toggle(this)
            (findViewById(R.id.btn_format_toggle) as TextView).text = TimeFormatHelper.toggleLabel(this)
            val today = cachedToday
            val nextKey = cachedNextKey
            if (today != null && nextKey != null) {
                buildTimesTable(findViewById(R.id.times_table) as LinearLayout, today, nextKey)
            }
        }

        (findViewById(R.id.btn_refresh) as TextView).setOnClickListener {
            PrayerUpdateWorker.enqueueImmediate(this)
            loadPreview()
        }

        PrayerUpdateWorker.schedulePeriodic(this)
        PrayerUpdateWorker.enqueueImmediate(this)
        loadPreview()
    }

    private fun applyStaticStrings() {
        (findViewById(R.id.btn_lang_toggle) as TextView).text = getString(R.string.lang_toggle_button)
        (findViewById(R.id.tv_app_title) as TextView).text = getString(R.string.app_name)
        (findViewById(R.id.btn_refresh) as TextView).text = getString(R.string.refresh_now)
        (findViewById(R.id.tv_table_header) as TextView).text = getString(R.string.today_times_header)
        (findViewById(R.id.tv_instructions) as TextView).text = getString(R.string.widget_instructions)
        (findViewById(R.id.btn_format_toggle) as TextView).text = TimeFormatHelper.toggleLabel(this)
        title = getString(R.string.app_name)
    }

    private fun loadPreview() {
        val nameTv = findViewById(R.id.tv_next_name) as TextView
        val countdownTv = findViewById(R.id.tv_next_countdown) as TextView
        val locationTv = findViewById(R.id.tv_location_line) as TextView
        val table = findViewById(R.id.times_table) as LinearLayout
        val progress = findViewById(R.id.progress_loading) as ProgressBar

        nameTv.text = getString(R.string.loading)
        countdownTv.text = ""
        progress.visibility = View.VISIBLE
        table.removeAllViews()

        // No kotlinx.coroutines available (not on the classpath in this build) — use a
        // plain background thread + runOnUiThread-style Handler post instead.
        Thread {
            val today = PrayerRepository(this@MainActivity).getTodayTimings()

            mainHandler.post {
                if (isFinishing) return@post
                progress.visibility = View.GONE

                if (today == null) {
                    nameTv.text = getString(R.string.connection_error)
                    countdownTv.text = getString(R.string.check_internet)
                    locationTv.text = ""
                    return@post
                }

                val next = PrayerLogic.findNext(today, AzanScheduler.peekTomorrowFajrMillis(this@MainActivity))
                val remaining = PrayerLogic.formatCountdown(next.whenMillis - System.currentTimeMillis())
                cachedToday = today
                cachedNextKey = next.key

                nameTv.text = "🕌 ${getString(R.string.next_prayer_label)}: ${getString(next.key.nameResId)}"
                countdownTv.text = remaining
                locationTv.text = listOf(today.cityName, today.hijriDate)
                    .filter { it.isNotBlank() }
                    .joinToString(" · ")

                buildTimesTable(table, today, next.key)
            }
        }.start()
    }

    private fun buildTimesTable(container: LinearLayout, today: DayTimings, nextKey: PrayerKey) {
        container.removeAllViews()
        val order = listOf(
            PrayerKey.FAJR, PrayerKey.SHUROUQ, PrayerKey.DHUHR,
            PrayerKey.ASR, PrayerKey.MAGHRIB, PrayerKey.ISHA
        )
        val isRtl = LocaleHelper.isRtl(this)

        for ((index, key) in order.withIndex()) {
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
                )
                setPadding(0, dp(11), 0, dp(11))
            }

            val isNext = key == nextKey
            val textColor = resources.getColor(if (isNext) R.color.gold_light else R.color.cream)
            val marker = if (isNext) (if (isRtl) "◀ " else "▶ ") else ""

            val nameTv = TextView(this).apply {
                text = marker + getString(key.nameResId)
                textSize = 16f
                setTextColor(textColor)
                if (isNext) setTypeface(null, Typeface.BOLD)
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            }

            val timeTv = TextView(this).apply {
                text = TimeFormatHelper.format(this@MainActivity, today.timeFor(key))
                textSize = 16f
                setTextColor(textColor)
                gravity = Gravity.END
                if (isNext) setTypeface(null, Typeface.BOLD)
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            }

            row.addView(nameTv)
            row.addView(timeTv)
            container.addView(row)

            if (index != order.size - 1) {
                val divider = View(this).apply {
                    layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(1))
                    setBackgroundColor(Color.parseColor("#33FFFFFF"))
                }
                container.addView(divider)
            }
        }
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()
}
