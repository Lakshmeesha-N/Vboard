package app.vboard

import android.view.KeyEvent
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

    fun performEnter(inputType: Int, imeOptions: Int): Boolean {
        val ic = connection() ?: return false
        val isMultiLine = (inputType and EditorInfo.TYPE_MASK_CLASS) == EditorInfo.TYPE_CLASS_TEXT &&
            (inputType and (EditorInfo.TYPE_TEXT_FLAG_MULTI_LINE or EditorInfo.TYPE_TEXT_VARIATION_LONG_MESSAGE)) != 0
        val action = imeOptions and EditorInfo.IME_MASK_ACTION
        return when (KeyLayouts.decideEnterBehavior(isMultiLine, action)) {
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
        ic.sendKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_ENTER))
        ic.sendKeyEvent(KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_ENTER))
    }
}
