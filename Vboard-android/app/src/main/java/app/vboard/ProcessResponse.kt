package app.vboard

import org.json.JSONObject

/** Mirrors `ActionModel` in contract/openapi.json. F5 applies only `insert`. */
data class ActionModel(
    val action: String,
    val text: String,
    val find: String?,
    val which: String?,
)

/** Subset of `ProcessResponse` the keyboard acts on. */
data class ProcessResponse(
    val transcript: String,
    val action: ActionModel?,
    val usedFallback: Boolean,
    val note: String?,
)

/**
 * Pure `ProcessResponse` JSON parser (no Android imports, JVM-tested).
 * Returns null when the body is not usable JSON. Unknown action names and
 * actions missing `text` degrade to `action = null` (change nothing).
 */
object ProcessResponseParser {

    fun parse(json: String): ProcessResponse? {
        val root = try {
            JSONObject(json)
        } catch (_: Exception) {
            return null
        }
        return ProcessResponse(
            transcript = root.optString("transcript", ""),
            action = root.optJSONObject("action")?.let(::parseAction),
            usedFallback = root.optBoolean("used_fallback", false),
            note = root.optString("note", "").ifEmpty { null },
        )
    }

    private fun parseAction(obj: JSONObject): ActionModel? {
        val kind = obj.optString("action", "")
        if (kind != "insert" && kind != "replace" && kind != "rewrite") return null
        val text = obj.optString("text", null as String?) ?: return null
        return ActionModel(
            action = kind,
            text = text,
            find = obj.optString("find", null as String?),
            which = obj.optString("which", null as String?),
        )
    }
}
