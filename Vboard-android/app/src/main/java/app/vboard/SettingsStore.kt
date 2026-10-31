package app.vboard

import android.content.Context
import android.content.SharedPreferences
import android.net.Uri
import androidx.core.content.edit
import java.util.UUID

class SettingsStore(context: Context) {
    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    private val idPrefs: SharedPreferences =
        context.getSharedPreferences(PREFS_ID_NAME, Context.MODE_PRIVATE)

    fun getLanguagesCsv(): String? = prefs.getString(KEY_LANGUAGES, null)

    fun getLanguages(): List<String> = LanguageList.parse(getLanguagesCsv())

    fun hasLanguages(): Boolean = LanguageList.hasLanguages(getLanguagesCsv())

    fun setLanguagesCsv(csv: String?): Boolean {
        if (!LanguageList.hasLanguages(csv)) return false
        prefs.edit { putString(KEY_LANGUAGES, csv) }
        return true
    }

    fun getBackendUrl(): String =
        prefs.getString(KEY_BACKEND_URL, DEFAULT_BACKEND_URL) ?: DEFAULT_BACKEND_URL

    fun setBackendUrl(raw: String): Boolean {
        val url = raw.trim().trimEnd('/')
        if (url.isEmpty() || url.length > MAX_BACKEND_URL_LENGTH) return false
        if (url.any { it.isWhitespace() }) return false
        val lower = url.lowercase()
        if (!lower.startsWith("http://") && !lower.startsWith("https://")) return false
        val parsed = Uri.parse(url)
        if (parsed.host.isNullOrEmpty()) return false
        if (parsed.encodedUserInfo != null) return false
        prefs.edit { putString(KEY_BACKEND_URL, url) }
        return true
    }

    fun getDeviceId(): String {
        val existing = idPrefs.getString(KEY_DEVICE_ID, null)
        if (!existing.isNullOrBlank()) {
            try {
                UUID.fromString(existing)
                return existing
            } catch (_: IllegalArgumentException) {
            }
        }
        val fresh = UUID.randomUUID().toString()
        idPrefs.edit { putString(KEY_DEVICE_ID, fresh) }
        return fresh
    }

    fun wasMicRequested(): Boolean = prefs.getBoolean(KEY_MIC_REQUESTED, false)

    fun setMicRequested() {
        prefs.edit { putBoolean(KEY_MIC_REQUESTED, true) }
    }

    companion object {
        const val PREFS_NAME = "vboard"
        const val PREFS_ID_NAME = "vboard_id"
        const val KEY_LANGUAGES = "languages"
        const val KEY_BACKEND_URL = "backend_url"
        const val KEY_DEVICE_ID = "device_id"
        const val KEY_MIC_REQUESTED = "mic_requested"
        const val DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
        const val MAX_BACKEND_URL_LENGTH = 2048
    }
}
