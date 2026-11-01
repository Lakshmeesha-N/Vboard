package app.vboard

import org.json.JSONObject

/** Mirrors `AgentResponse` in contract/openapi.json. Never carries `languages`. */
data class AgentResponse(
    val text: String,
    val usedSearch: Boolean,
    val rounds: Int,
    val note: String?,
)

/**
 * Pure `AgentResponse` JSON parser (no Android imports, JVM-tested).
 * Returns null when the body is not usable JSON or misses required fields.
 * Never logs content.
 */
object AgentResponseParser {

    fun parse(json: String): AgentResponse? {
        val root = try {
            JSONObject(json)
        } catch (_: Exception) {
            return null
        }
        if (!root.has("text") || !root.has("used_search") || !root.has("rounds")) return null
        val text = root.optString("text", null as String?) ?: return null
        val note = root.optString("note", null as String?)
        return AgentResponse(
            text = text,
            usedSearch = root.optBoolean("used_search", false),
            rounds = root.optInt("rounds", 0),
            note = note,
        )
    }

    /** Extracts the first validation message from a 422 `HTTPValidationError` body. */
    fun parseErrorDetail(json: String): String? {
        val root = try {
            JSONObject(json)
        } catch (_: Exception) {
            return null
        }
        val arr = root.optJSONArray("detail") ?: return root.optString("detail", null as String?)
        if (arr.length() == 0) return null
        val msg = arr.optJSONObject(0)?.optString("msg", null as String?)
        return msg?.ifEmpty { null }
    }
}
