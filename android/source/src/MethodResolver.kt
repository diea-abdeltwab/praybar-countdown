package com.prayer.countdown

/**
 * Picks the prayer-time calculation authority (and Asr juristic school) that best matches
 * the user's country, so the app gives locally-correct times no matter who installs it —
 * not just in Egypt. Falls back to the Muslim World League method (the most globally
 * recognized default) for any country not explicitly listed.
 */
object MethodResolver {

    data class Params(val method: Int, val school: Int)

    // Aladhan method IDs: 1 Karachi, 2 ISNA, 3 Muslim World League, 4 Umm Al-Qura,
    // 5 Egyptian General Authority, 7 Tehran, 8 Gulf Region, 9 Kuwait, 10 Qatar,
    // 11 Singapore, 12 UOIF (France), 13 Diyanet (Turkey), 14 Russia.
    private val METHOD_BY_COUNTRY = mapOf(
        "EG" to 5,
        "SA" to 4,
        "AE" to 8, "BH" to 8, "OM" to 8,
        "KW" to 9,
        "QA" to 10,
        "PK" to 1, "IN" to 1, "BD" to 1, "AF" to 1, "BT" to 1, "NP" to 1, "LK" to 1,
        "US" to 2, "CA" to 2,
        "TR" to 13,
        "IR" to 7,
        "SG" to 11,
        "FR" to 12,
        "RU" to 14
    )

    // Countries where the Hanafi Asr convention (school=1) is the common local practice.
    private val HANAFI_COUNTRIES = setOf("PK", "IN", "BD", "AF", "BT", "NP", "LK")

    fun resolve(countryCode: String): Params {
        val code = countryCode.toUpperCase(java.util.Locale.US)
        val method = METHOD_BY_COUNTRY[code] ?: 3 // Muslim World League — safe global default
        val school = if (HANAFI_COUNTRIES.contains(code)) 1 else 0
        return Params(method, school)
    }
}
