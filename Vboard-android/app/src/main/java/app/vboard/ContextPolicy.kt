package app.vboard

/**
 * Pure textbox-context policy (no Android imports, JVM-tested).
 * Framework `EditorInfo` constants are mirrored locally so unit tests
 * never touch `android.jar` stubs.
 */
object ContextPolicy {

    const val CONTEXT_MAX_CHARS = 10_000

    // EditorInfo.TYPE_* mirrors.
    private const val TYPE_MASK_CLASS = 0x0000000f
    private const val TYPE_MASK_VARIATION = 0x00000ff0
    private const val TYPE_CLASS_TEXT = 0x00000001
    private const val TYPE_CLASS_NUMBER = 0x00000002
    private const val TYPE_TEXT_VARIATION_PASSWORD = 0x00000080
    private const val TYPE_TEXT_VARIATION_VISIBLE_PASSWORD = 0x00000090
    private const val TYPE_TEXT_VARIATION_WEB_PASSWORD = 0x000000e0
    private const val TYPE_NUMBER_VARIATION_PASSWORD = 0x00000010

    /**
     * True for password/PIN fields, where context must stay empty.
     * Visible-password counts: still a credential field.
     */
    fun isPasswordInputType(inputType: Int): Boolean {
        val variation = inputType and TYPE_MASK_VARIATION
        return when (inputType and TYPE_MASK_CLASS) {
            TYPE_CLASS_TEXT ->
                variation == TYPE_TEXT_VARIATION_PASSWORD ||
                    variation == TYPE_TEXT_VARIATION_VISIBLE_PASSWORD ||
                    variation == TYPE_TEXT_VARIATION_WEB_PASSWORD
            TYPE_CLASS_NUMBER -> variation == TYPE_NUMBER_VARIATION_PASSWORD
            else -> false
        }
    }

    /**
     * Joins text around the cursor, capped at [maxChars]. Keeps the tail of
     * [before] and the head of [after] (nearest the cursor wins); null-safe.
     */
    fun capContext(before: String?, after: String?, maxChars: Int): String {
        val tail = before ?: ""
        val head = after ?: ""
        if (tail.length + head.length <= maxChars) return tail + head
        val keepHead = (maxChars / 2).coerceAtMost(head.length)
        val keepTail = (maxChars - keepHead).coerceAtMost(tail.length)
        return tail.takeLast(keepTail) + head.take(keepHead)
    }
}
