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
}
