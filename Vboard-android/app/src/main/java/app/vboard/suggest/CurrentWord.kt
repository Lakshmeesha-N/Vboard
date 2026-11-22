package app.vboard.suggest

/**
 * Extracts the word currently being typed from the text before the cursor.
 * Pure Kotlin, no Android imports.
 */
object CurrentWord {

    /**
     * Returns the trailing run of ASCII letters and apostrophes,
     * with stray apostrophes trimmed from both ends.
     * "" means there is no completable word (space, punctuation,
     * digits, newline, empty box).
     */
    fun extract(before: CharSequence): String {
        var start = before.length
        while (start > 0 && isWordChar(before[start - 1])) {
            start--
        }
        return before.substring(start, before.length).trim('\'')
    }

    private fun isWordChar(c: Char): Boolean =
        c in 'a'..'z' || c in 'A'..'Z' || c == '\''
}
