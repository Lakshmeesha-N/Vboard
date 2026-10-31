package app.vboard

/**
 * Pure rewrite/insert decision logic (no Android imports, JVM-tested).
 * Android side ([TextBoxEditor], `KeyboardService`) handles the real
 * cursor, batch edits, Undo state, and hints.
 */
object ActionApplier {

    enum class Outcome {
        INSERTED,
        REWRITTEN,
        NOTHING_CHANGED,
        REPLACE_UNSUPPORTED,
        NULL_ACTION,
        TOO_LONG,
    }

    data class Result(val newText: String, val outcome: Outcome)

    /** Testable length guard: full box over the read cap must never rewrite. */
    fun isTooLong(full: String, maxChars: Int = ContextPolicy.CONTEXT_MAX_CHARS): Boolean =
        full.length > maxChars

    /**
     * Pure textbox projection. `box` is the full text
     * (before + selected + after). Insert appends (the real cursor
     * is handled by `commitText` on Android).
     */
    fun applyAction(box: String, action: ActionModel?): Result {
        if (action == null) return Result(box, Outcome.NULL_ACTION)
        return when (action.action) {
            "insert" -> Result(box + action.text, Outcome.INSERTED)
            "rewrite" -> {
                if (isTooLong(box)) return Result(box, Outcome.TOO_LONG)
                if (box == action.text) return Result(box, Outcome.NOTHING_CHANGED)
                Result(action.text, Outcome.REWRITTEN)
            }
            else -> Result(box, Outcome.REPLACE_UNSUPPORTED)
        }
    }
}
