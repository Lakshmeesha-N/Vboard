package app.vboard

import android.inputmethodservice.InputMethodService
import android.os.Build
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Toast

class KeyboardService : InputMethodService(), KeyboardView.Listener, TopBarView.Listener {

    private var keyboardView: KeyboardView? = null
    private var editor: TextBoxEditor? = null
    private var imeOptions: Int = EditorInfo.IME_NULL

    override fun onCreateInputView(): View {
        editor = TextBoxEditor { currentInputConnection }
        return KeyboardView(this).also {
            it.listener = this
            it.topBarListener = this
            keyboardView = it
        }
    }

    override fun onStartInputView(info: EditorInfo?, restarting: Boolean) {
        super.onStartInputView(info, restarting)
        imeOptions = info?.imeOptions ?: EditorInfo.IME_NULL
    }

    override fun onFinishInputView(finishingInput: Boolean) {
        super.onFinishInputView(finishingInput)
        keyboardView?.resetShift()
    }

    override fun onDestroy() {
        keyboardView?.listener = null
        keyboardView?.topBarListener = null
        keyboardView = null
        editor = null
        super.onDestroy()
    }

    override fun onText(text: String) {
        editor?.commitText(text)
    }

    override fun onBackspace() {
        editor?.deleteCodePointBefore()
    }

    override fun onEnter() {
        editor?.performEnter(imeOptions)
    }

    override fun onShiftChanged(capsLock: Boolean) = Unit

    override fun onGlobe() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            switchToNextInputMethod(false)
        }
    }

    override fun onSymbolsStub() {
        Toast.makeText(this, "Symbols in F2", Toast.LENGTH_SHORT).show()
    }

    override fun onVoiceClick() {
        Toast.makeText(this, "Voice recording lands in F4", Toast.LENGTH_SHORT).show()
    }

    override fun onAiClick() {
        Toast.makeText(this, "AI actions land in F8", Toast.LENGTH_SHORT).show()
    }
}
