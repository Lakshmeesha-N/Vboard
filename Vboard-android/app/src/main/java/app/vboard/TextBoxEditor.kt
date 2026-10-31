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
