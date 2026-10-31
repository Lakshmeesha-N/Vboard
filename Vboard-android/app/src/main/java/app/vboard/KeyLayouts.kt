package app.vboard

object KeyLayouts {
    val NumberRow = listOf("1", "2", "3", "4", "5", "6", "7", "8", "9", "0")
    val RowTop = listOf("Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P")
    val RowMiddle = listOf("A", "S", "D", "F", "G", "H", "J", "K", "L")
    val RowBottom = listOf("Z", "X", "C", "V", "B", "N", "M")

    const val KEY_SHIFT = "SHIFT"
    const val KEY_BACKSPACE = "BACKSPACE"
    const val KEY_SYMBOLS = "?123"
    const val KEY_COMMA = ","
    const val KEY_SPACE = "SPACE"
    const val KEY_PERIOD = "."
    const val KEY_ENTER = "ENTER"

    const val SPACE_LABEL = "English (US)"
    const val SHIFT_LABEL = "⇧"
    const val CAPS_LABEL = "⇪"
    const val BACKSPACE_LABEL = "⌫"
    const val ENTER_LABEL = "⏎"

    /** Toggle caps mapping kept pure for JVM tests; non-letters pass through. */
    fun applyCaps(base: String, capsOn: Boolean): String {
        if (base.length == 1 && base[0].isLetter()) {
            return if (capsOn) base.uppercase() else base.lowercase()
        }
        return base
    }

    enum class EnterBehavior { NEW_LINE, EDITOR_ACTION, KEY_EVENT }

    // Mirrors of EditorInfo.IME_ACTION_* ids so the decision stays JVM-testable
    // without Android classes. Values match android.view.inputmethod.EditorInfo.
    const val IME_ACTION_UNSPECIFIED_ID = 0
    const val IME_ACTION_NONE_ID = 1

    /**
     * Pure Enter-key policy: NO_ENTER_ACTION always inserts a newline; a real
     * action (GO, SEARCH, SEND, NEXT, DONE, PREVIOUS) tries the editor action
     * first; with no action (NONE, UNSPECIFIED) multi-line fields get a
     * newline and single-line fields get a physical Enter key event.
     */
    fun decideEnterBehavior(isMultiLine: Boolean, imeActionId: Int, noEnterAction: Boolean): EnterBehavior = when {
        noEnterAction -> EnterBehavior.NEW_LINE
        imeActionId != IME_ACTION_UNSPECIFIED_ID && imeActionId != IME_ACTION_NONE_ID -> EnterBehavior.EDITOR_ACTION
        isMultiLine -> EnterBehavior.NEW_LINE
        else -> EnterBehavior.KEY_EVENT
    }

    /** Pure hold-to-repeat timing so the policy is JVM-testable without Android. */
    object RepeatTiming {
        const val INITIAL_DELAY_MS = 400L
        const val INTERVAL_MS = 50L

        fun delayForTick(tickIndex: Int): Long = if (tickIndex == 0) INITIAL_DELAY_MS else INTERVAL_MS

        fun shouldContinue(hasTextBeforeCursor: Boolean): Boolean = hasTextBeforeCursor
    }
}
