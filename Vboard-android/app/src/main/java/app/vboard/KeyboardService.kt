package app.vboard

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.inputmethodservice.InputMethodService
import android.os.Build
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.core.view.WindowCompat
import java.util.Arrays

class KeyboardService : InputMethodService(), KeyboardView.Listener, TopBarView.Listener {

    private var keyboardView: KeyboardView? = null
    private var editor: TextBoxEditor? = null
    private var imeOptions: Int = EditorInfo.IME_NULL
    private var recorder: Recorder? = null
    private var recording = false

    /** Take confirmed with ✓, held in RAM for F5 to send. */
    private var pendingWav: ByteArray? = null

    private val idleAfterProcessing = Runnable {
        if (recording) return@Runnable
        keyboardView?.showIdleBar()
    }

    override fun onCreate() {
        super.onCreate()
        window?.window?.let { WindowCompat.setDecorFitsSystemWindows(it, false) }
    }

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
        keyboardView?.refreshInsets()
    }

    override fun onFinishInputView(finishingInput: Boolean) {
        super.onFinishInputView(finishingInput)
        keyboardView?.cancelKeyRepeats()
        keyboardView?.resetShift()
        stopRecordingSilently()
        keyboardView?.removeCallbacks(idleAfterProcessing)
        keyboardView?.showIdleBar()
    }

    override fun onDestroy() {
        keyboardView?.removeCallbacks(idleAfterProcessing)
        stopRecordingSilently()
        clearPendingWav()
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

    override fun onBackspaceRepeat(): Boolean {
        val ed = editor ?: return false
        val keepGoing = KeyLayouts.RepeatTiming.shouldContinue(ed.hasTextBeforeCursor())
        if (keepGoing) ed.deleteCodePointBefore()
        return keepGoing
    }

    override fun onEnter() {
        val inputType = currentInputEditorInfo?.inputType ?: EditorInfo.TYPE_NULL
        editor?.performEnter(inputType, imeOptions)
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
        if (recording) return
        if (!hasMicPermission()) {
            Toast.makeText(this, "Microphone needed for voice. Opening setup.", Toast.LENGTH_SHORT).show()
            startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            return
        }
        clearPendingWav()
        val rec = Recorder(
            onAmplitude = { raw -> keyboardView?.post { keyboardView?.setRecordingAmplitude(raw) } },
            onAutoStop = { keyboardView?.post { finishRecording(auto = true) } },
        )
        when (rec.start()) {
            Recorder.StartResult.Started -> {
                recorder = rec
                recording = true
                keyboardView?.showRecordingBar()
            }
            Recorder.StartResult.Failed -> {
                Toast.makeText(this, "Microphone unavailable. Try again.", Toast.LENGTH_SHORT).show()
            }
        }
    }

    override fun onAiClick() {
        Toast.makeText(this, "AI actions land in F8", Toast.LENGTH_SHORT).show()
    }

    override fun onCancel() {
        if (!recording) return
        stopRecordingSilently()
        clearPendingWav()
        keyboardView?.showIdleBar()
    }

    override fun onConfirm() {
        if (!recording) return
        finishRecording(auto = false)
    }

    private fun finishRecording(auto: Boolean) {
        if (!recording) return
        recording = false
        val rec = recorder
        recorder = null
        val wav = try {
            rec?.stop()
        } catch (_: Exception) {
            try {
                rec?.cancel()
            } catch (_: Exception) {
                // Teardown must never crash the IME.
            }
            null
        }
        if (wav == null) {
            keyboardView?.showIdleBar()
            if (!auto) Toast.makeText(this, "Too short. Hold the thought a beat longer.", Toast.LENGTH_SHORT).show()
            return
        }
        pendingWav = wav
        keyboardView?.showProcessingBar()
        Toast.makeText(this, "Recorded. Send lands in F5.", Toast.LENGTH_SHORT).show()
        keyboardView?.removeCallbacks(idleAfterProcessing)
        keyboardView?.postDelayed(idleAfterProcessing, PROCESSING_HINT_MS)
    }

    private fun stopRecordingSilently() {
        recording = false
        val rec = recorder
        recorder = null
        try {
            rec?.cancel()
        } catch (_: Exception) {
            // Teardown must never crash the IME.
        }
    }

    private fun clearPendingWav() {
        val wav = pendingWav
        pendingWav = null
        if (wav != null) Arrays.fill(wav, 0)
    }

    private fun hasMicPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED

    companion object {
        private const val PROCESSING_HINT_MS = 1200L
    }
}
