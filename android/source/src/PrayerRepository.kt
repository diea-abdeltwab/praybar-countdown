package com.prayer.countdown

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Resolved device location + country, used to pick both coordinates and calculation method. */
data class LocationInfo(val lat: Double, val lon: Double, val city: String, val countryCode: String)

class PrayerRepository(context: Context) {

    private val prefs: SharedPreferences =
        context.getSharedPreferences("prayer_cache", Context.MODE_PRIVATE)

    companion object {
        private const val TAG = "PrayerRepository"
        private const val KEY_DATE = "cache_date"
        private const val KEY_TIMINGS = "cache_timings_json"
        private const val KEY_LAT = "cache_lat"
        private const val KEY_LON = "cache_lon"
        private const val KEY_COUNTRY = "cache_country"
    }

    fun getTodayTimings(): DayTimings? {
        val todayIso = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
        val fresh = tryFetchFresh(todayIso)
        if (fresh != null) return fresh
        if (prefs.getString(KEY_DATE, null) == todayIso) {
            return readCache(todayIso)
        }
        return null
    }

    fun getTimingsFor(dateIso: String, lat: Double, lon: Double, countryCode: String): DayTimings? {
        return try {
            val params = MethodResolver.resolve(countryCode)
            fetchAladhan(dateIso, lat, lon, params.method, params.school)
        } catch (e: Exception) {
            Log.w(TAG, "getTimingsFor failed", e)
            null
        }
    }

    fun getLastKnownLocation(): LocationInfo? {
        val lat = prefs.getFloat(KEY_LAT, Float.NaN)
        val lon = prefs.getFloat(KEY_LON, Float.NaN)
        if (lat.isNaN() || lon.isNaN()) return null
        val country = prefs.getString(KEY_COUNTRY, "") ?: ""
        return LocationInfo(lat.toDouble(), lon.toDouble(), "", country)
    }

    private fun tryFetchFresh(todayIso: String): DayTimings? {
        return try {
            val loc = fetchIpLocation()
            val params = MethodResolver.resolve(loc.countryCode)
            val timings = fetchAladhan(todayIso, loc.lat, loc.lon, params.method, params.school, loc.city)
            writeCache(todayIso, timings, loc)
            timings
        } catch (e: Exception) {
            Log.w(TAG, "Live fetch failed, will try cache", e)
            null
        }
    }

    private fun fetchIpLocation(): LocationInfo {
        val json = httpGetJson("https://ipwho.is/")
        if (!json.optBoolean("success", true)) throw Exception("ipwho.is reported failure")
        val lat = json.getDouble("latitude")
        val lon = json.getDouble("longitude")
        val city = json.optString("city", "")
        val countryCode = json.optString("country_code", "")
        return LocationInfo(lat, lon, city, countryCode)
    }

    private fun fetchAladhan(
        dateIso: String, lat: Double, lon: Double, method: Int, school: Int, city: String = ""
    ): DayTimings {
        val isoFmt = SimpleDateFormat("yyyy-MM-dd", Locale.US)
        val dmyFmt = SimpleDateFormat("dd-MM-yyyy", Locale.US)
        val dmy = dmyFmt.format(isoFmt.parse(dateIso)!!)
        val url = "https://api.aladhan.com/v1/timings/$dmy" +
            "?latitude=$lat&longitude=$lon&method=$method&school=$school"
        val json = httpGetJson(url)
        val data = json.getJSONObject("data")
        val timings = data.getJSONObject("timings")
        val hijri = data.getJSONObject("date").getJSONObject("hijri")
        val hijriStr = hijri.getString("day") + " " +
            hijri.getJSONObject("month").getString("ar") + " " + hijri.getString("year")

        return DayTimings(
            fajr = clean(timings.getString("Fajr")),
            shurouq = clean(timings.getString("Sunrise")),
            dhuhr = clean(timings.getString("Dhuhr")),
            asr = clean(timings.getString("Asr")),
            maghrib = clean(timings.getString("Maghrib")),
            isha = clean(timings.getString("Isha")),
            dateIso = dateIso,
            hijriDate = hijriStr,
            cityName = city
        )
    }

    private fun clean(v: String): String {
        val cut = v.substringBefore(" ")
        return if (cut.length > 5) cut.substring(0, 5) else cut
    }

    private fun writeCache(dateIso: String, t: DayTimings, loc: LocationInfo) {
        val obj = JSONObject()
        obj.put("fajr", t.fajr); obj.put("shurouq", t.shurouq); obj.put("dhuhr", t.dhuhr)
        obj.put("asr", t.asr); obj.put("maghrib", t.maghrib); obj.put("isha", t.isha)
        obj.put("hijri", t.hijriDate); obj.put("city", t.cityName)
        prefs.edit()
            .putString(KEY_DATE, dateIso)
            .putString(KEY_TIMINGS, obj.toString())
            .putFloat(KEY_LAT, loc.lat.toFloat())
            .putFloat(KEY_LON, loc.lon.toFloat())
            .putString(KEY_COUNTRY, loc.countryCode)
            .apply()
    }

    private fun readCache(dateIso: String): DayTimings? {
        val json = prefs.getString(KEY_TIMINGS, null) ?: return null
        return try {
            val obj = JSONObject(json)
            DayTimings(
                fajr = obj.getString("fajr"),
                shurouq = obj.getString("shurouq"),
                dhuhr = obj.getString("dhuhr"),
                asr = obj.getString("asr"),
                maghrib = obj.getString("maghrib"),
                isha = obj.getString("isha"),
                dateIso = dateIso,
                hijriDate = obj.optString("hijri", ""),
                cityName = obj.optString("city", "")
            )
        } catch (e: Exception) {
            null
        }
    }

    private fun httpGetJson(urlStr: String): JSONObject {
        val conn = URL(urlStr).openConnection() as HttpURLConnection
        conn.connectTimeout = 8000
        conn.readTimeout = 8000
        conn.setRequestProperty("User-Agent", "PrayerCountdownWidget/1.0")
        conn.setRequestProperty("Accept", "application/json")
        try {
            val code = conn.responseCode
            if (code < 200 || code > 299) throw Exception("HTTP $code for $urlStr")
            val body = conn.inputStream.bufferedReader().use { it.readText() }
            return JSONObject(body)
        } finally {
            conn.disconnect()
        }
    }
}
