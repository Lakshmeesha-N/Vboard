package app.vboard

import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputConnection

class TextBoxEditor(private val connection: () -> InputConnection?) {

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

    fun performEnter(imeOptions: Int): Boolean {
        val ic = connection() ?: return false
        val action = imeOptions and EditorInfo.IME_MASK_ACTION
        return if (action != EditorInfo.IME_ACTION_NONE && action != EditorInfo.IME_ACTION_UNSPECIFIED) {
            ic.performEditorAction(action)
            true
        } else {
            commitText("\n")
            false
        }
    }
}
