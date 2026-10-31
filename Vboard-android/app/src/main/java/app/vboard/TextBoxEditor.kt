package app.vboard

import android.view.KeyEvent
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputConnection

class TextBoxEditor(private val connection: () -> InputConnection?) {

    // Preallocated so the key touch path never allocates.
    private val enterDown = KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_ENTER)
    private val enterUp = KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_ENTER)

    fun commitText(text: String) {
        val ic = connection() ?: return
        ic.beginBatchEdit()
        ic.commitText(text, 1)
        ic.endBatchEdit()
    }

    fun deleteCodePointBefore() {
        val ic = connection() ?: return
        ic.beginBatchEdit()
        ic.deleteSurroundingTextInCodePoints(1, 0)
        ic.endBatchEdit()
    }

    fun performEnter(inputType: Int, imeOptions: Int): Boolean {
        val ic = connection() ?: return false
        val isMultiLine = (inputType and EditorInfo.TYPE_MASK_CLASS) == EditorInfo.TYPE_CLASS_TEXT &&
            (inputType and (EditorInfo.TYPE_TEXT_FLAG_MULTI_LINE or EditorInfo.TYPE_TEXT_VARIATION_LONG_MESSAGE)) != 0
        val noEnterAction = (imeOptions and EditorInfo.IME_FLAG_NO_ENTER_ACTION) != 0
        val action = imeOptions and EditorInfo.IME_MASK_ACTION
        return when (KeyLayouts.decideEnterBehavior(isMultiLine, action, noEnterAction)) {
            KeyLayouts.EnterBehavior.NEW_LINE -> {
                commitText("\n")
                true
            }
            KeyLayouts.EnterBehavior.EDITOR_ACTION -> {
                if (!ic.performEditorAction(action)) sendEnterKey(ic)
                true
            }
            KeyLayouts.EnterBehavior.KEY_EVENT -> {
                sendEnterKey(ic)
                true
            }
        }
    }

    private fun sendEnterKey(ic: InputConnection) {
        ic.sendKeyEvent(enterDown)
        ic.sendKeyEvent(enterUp)
    }

    /** True when at least one char sits before the cursor; only the length is used. */
    fun hasTextBeforeCursor(): Boolean =
        connection()?.getTextBeforeCursor(1, 0)?.isNotEmpty() == true

    /** Full textbox snapshot: before + selected + after. */
    data class FullText(
        val before: String,
        val selected: String,
        val after: String,
        val full: String,
        /** Char index to collapse a selection to (before + selected). */
        val endCharIndex: Int,
        /** False when any read threw or returned an uncertain shape. */
        val reliable: Boolean,
    )

    /**
     * Reads the full box including the selection. Returns
     * `reliable = false` when anything is uncertain; callers must
     * skip the rewrite then. Never logs content.
     */
    fun readFullText(inputType: Int, maxChars: Int): FullText {
        if (ContextPolicy.isPasswordInputType(inputType)) {
            return FullText("", "", "", "", 0, true)
        }
        val ic = connection() ?: return FullText("", "", "", "", 0, false)
        return try {
            val before = try {
                ic.getTextBeforeCursor(maxChars, 0)?.toString()
            } catch (_: Exception) {
                null
            } ?: return FullText("", "", "", "", 0, false)
            val selected = try {
                ic.getSelectedText(0)?.toString() ?: ""
            } catch (_: Exception) {
                return FullText("", "", "", "", 0, false)
            }
            val after = try {
                ic.getTextAfterCursor(maxChars, 0)?.toString()
            } catch (_: Exception) {
                null
            } ?: return FullText("", "", "", "", 0, false)
            FullText(before, selected, after, before + selected + after, before.length + selected.length, true)
        } catch (_: Exception) {
            FullText("", "", "", "", 0, false)
        }
    }

    /** Collapses an active selection to its end so deletes run around one cursor. */
    fun collapseSelectionTo(endCharIndex: Int): Boolean {
        val ic = connection() ?: return false
        return try {
            ic.setSelection(endCharIndex, endCharIndex)
        } catch (_: Exception) {
            false
        }
    }

    fun codePointCount(text: String): Int =
        try {
            text.codePointCount(0, text.length)
        } catch (_: Exception) {
            text.length
        }

    /**
     * Replaces the entire box around an already-collapsed cursor.
     * Counts are in code points (Kannada combining characters).
     */
    fun rewriteFull(beforeCodePoints: Int, afterCodePoints: Int, newText: String): Boolean {
        val ic = connection() ?: return false
        ic.beginBatchEdit()
        return try {
            ic.deleteSurroundingTextInCodePoints(beforeCodePoints, afterCodePoints)
            ic.commitText(newText, 1)
            true
        } catch (_: Exception) {
            false
        } finally {
            try {
                ic.endBatchEdit()
            } catch (_: Exception) {
                // Teardown must never crash the IME.
            }
        }
    }

    /** Puts the cursor at the end of `charLength` chars (used after Undo). */
    fun moveCursorToEnd(charLength: Int): Boolean {
        val ic = connection() ?: return false
        return try {
            ic.setSelection(charLength, charLength)
        } catch (_: Exception) {
            false
        }
    }

    /**
     * Reads up to [maxChars] of textbox context (before + after cursor).
     * Returns "" in password fields or when unreadable. Callers must never log it.
     */
    fun readContextText(inputType: Int, maxChars: Int): String {
        if (ContextPolicy.isPasswordInputType(inputType)) return ""
        val ic = connection() ?: return ""
        val before = try {
            ic.getTextBeforeCursor(maxChars, 0)?.toString()
        } catch (_: Exception) {
            null
        }
        val after = try {
            ic.getTextAfterCursor(maxChars, 0)?.toString()
        } catch (_: Exception) {
            null
        }
        return ContextPolicy.capContext(before, after, maxChars)
    }
}
