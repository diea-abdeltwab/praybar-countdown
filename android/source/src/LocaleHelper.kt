package com.prayer.countdown

import android.content.Context
import android.content.res.Configuration
import android.content.res.Resources
import java.util.Locale

/**
 * The app supports Arabic and English regardless of the device's system language.
 * The chosen language is stored once and used everywhere: the widgets, the azan
 * notification, and the main screen — by building a small locale-wrapped Resources
 * object and resolving all display strings through it ourselves.
 */
object LocaleHelper {

    private const val PREFS = "app_settings"
    private const val KEY_LANG = "language"

    fun getLanguage(context: Context): String {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val saved = prefs.getString(KEY_LANG, null)
        if (saved != null) return saved
        val deviceLang = context.resources.configuration.locale.language
        return if (deviceLang == "ar") "ar" else "en"
    }

    fun setLanguage(context: Context, lang: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(KEY_LANG, lang).apply()
    }

    fun otherLanguage(context: Context): String = if (getLanguage(context) == "ar") "en" else "ar"

    fun isRtl(context: Context): Boolean = getLanguage(context) == "ar"

    /** A Context whose resources/configuration reflect the chosen app language. */
    fun localizedContext(context: Context): Context {
        val locale = Locale(getLanguage(context))
        val config = Configuration(context.resources.configuration)
        config.setLocale(locale)
        return context.createConfigurationContext(config)
    }

    /** Shortcut when only strings are needed (widgets, notifications). */
    fun localizedResources(context: Context): Resources = localizedContext(context).resources
}
