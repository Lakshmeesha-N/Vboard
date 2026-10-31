package app.vboard

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.inputmethodservice.InputMethodService
import android.net.Uri
import android.os.Build
import android.os.SystemClock
import android.util.Log
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.core.view.WindowCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Arrays
import kotlin.coroutines.cancellation.CancellationException

class KeyboardService : InputMethodService(), KeyboardView.Listener, TopBarView.Listener {

    private var keyboardView: KeyboardView? = null
    private var editor: TextBoxEditor? = null
    private var imeOptions: Int = EditorInfo.IME_NULL
    private var recorder: Recorder? = null
    private var recording = false

    /** Take confirmed with ✓, held in RAM until the send finishes. Zeroed after. */
    private var pendingWav: ByteArray? = null

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var settings: SettingsStore? = null
    private var backend: BackendClient? = null
    private var lastBackendUrl: String? = null
    private var sendJob: Job? = null

    /** True while a /v1/process round-trip is in flight; a second ✓ is ignored. */
    private var sending = false

    /** One-level Undo: full box text saved before an AI insert/rewrite. */
    private var undoText: String? = null

    /** Full box text snapshotted at ✓; rewrite applies only if it still matches. */
    private var snapshotFull = ""

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
        clearUndo()
        keyboardView?.refreshInsets()
    }

    override fun onFinishInputView(finishingInput: Boolean) {
        super.onFinishInputView(finishingInput)
        keyboardView?.cancelKeyRepeats()
        keyboardView?.resetShift()
        stopRecordingSilently()
        cancelSend()
        clearUndo()
        keyboardView?.showIdleBar()
    }

    override fun onDestroy() {
        stopRecordingSilently()
        cancelSend()
        clearPendingWav()
        serviceScope.cancel()
        keyboardView?.listener = null
        keyboardView?.topBarListener = null
        keyboardView = null
        editor = null
        super.onDestroy()
    }

    override fun onText(text: String) {
        clearUndo()
        editor?.commitText(text)
    }

    override fun onBackspace() {
        clearUndo()
        editor?.deleteCodePointBefore()
    }

    override fun onBackspaceRepeat(): Boolean {
        val ed = editor ?: return false
        val keepGoing = KeyLayouts.RepeatTiming.shouldContinue(ed.hasTextBeforeCursor())
        if (keepGoing) {
            clearUndo()
            ed.deleteCodePointBefore()
        }
        return keepGoing
    }

    override fun onEnter() {
        clearUndo()
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
            toast("Microphone needed for voice. Opening setup.")
            openSetup()
            return
        }
        if (!store().hasLanguages()) {
            toast("Pick your languages in the Vboard app")
            openSetup()
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

    override fun onUndo() {
        val ed = editor ?: return
        val restore = undoText ?: return
        clearUndo()
        val inputType = currentInputEditorInfo?.inputType ?: EditorInfo.TYPE_NULL
        val current = ed.readFullText(inputType, ContextPolicy.CONTEXT_MAX_CHARS)
        if (!current.reliable) {
            toast(MSG_SELECTION_UNSURE)
            return
        }
        if (current.selected.isNotEmpty() && !ed.collapseSelectionTo(current.endCharIndex)) {
            toast(MSG_SELECTION_UNSURE)
            return
        }
        val beforeCp = ed.codePointCount(current.before + current.selected)
        val afterCp = ed.codePointCount(current.after)
        if (!ed.rewriteFull(beforeCp, afterCp, restore)) {
            toast(MSG_SELECTION_UNSURE)
            return
        }
        ed.moveCursorToEnd(restore.length)
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
        val store = store()
        if (!store.hasLanguages()) {
            clearPendingWav()
            keyboardView?.showIdleBar()
            toast("Pick your languages in the Vboard app")
            openSetup()
            return
        }
        // Read the full textbox now, on the main thread, at the moment of ✓.
        val inputType = currentInputEditorInfo?.inputType ?: EditorInfo.TYPE_NULL
        val full = editor?.readFullText(inputType, ContextPolicy.CONTEXT_MAX_CHARS)
            ?: TextBoxEditor.FullText("", "", "", "", 0, false)
        if (!full.reliable) {
            clearPendingWav()
            keyboardView?.showIdleBar()
            toast(MSG_SELECTION_UNSURE)
            return
        }
        snapshotFull = full.full
        val contextText = if (full.full.length <= ContextPolicy.CONTEXT_MAX_CHARS) {
            full.full
        } else {
            ContextPolicy.capContext(full.before + full.selected, full.after, ContextPolicy.CONTEXT_MAX_CHARS)
        }
        keyboardView?.showProcessingBar()
        sendToBackend(store, contextText)
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

    private fun showUndo(previousFullText: String) {
        undoText = previousFullText
        keyboardView?.setUndoVisible(true)
    }

    private fun clearUndo() {
        undoText = null
        keyboardView?.setUndoVisible(false)
    }

    private fun sendToBackend(store: SettingsStore, contextText: String) {
        // Take ownership: null the slot now so the buffer we zero in
        // `finally` is always the one we sent, never a newer take.
        val wav = pendingWav
        pendingWav = null
        if (wav == null || sending) {
            if (wav == null) keyboardView?.showIdleBar()
            return
        }
        sending = true
        val url = store.getBackendUrl()
        if (backend == null || lastBackendUrl != url) {
            backend = BackendClient(url)
            lastBackendUrl = url
        }
        val client = backend
        if (client == null) {
            sending = false
            Arrays.fill(wav, 0)
            keyboardView?.showIdleBar()
            return
        }
        val languages = store.getLanguagesCsv().orEmpty()
        val deviceId = store.getDeviceId()
        // TEMPORARY debug: numbers and class names only, never user text.
        val uri = Uri.parse(url)
        Log.d(TAG, "send wavBytes=" + wav.size + " host=" + uri.host + " port=" + uri.port)
        toast("sending")
        sendJob?.cancel()
        sendJob = serviceScope.launch {
            val started = SystemClock.elapsedRealtime()
            val outcome: SendOutcome = try {
                val res = withContext(Dispatchers.IO) {
                    client.processAudio(wav, languages, contextText, deviceId)
                }
                Log.d(TAG, "got status=" + res.httpCode + " elapsedMs=" + (SystemClock.elapsedRealtime() - started))
                SendOutcome.Done(res.httpCode, ProcessResponseParser.parse(res.body))
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.d(TAG, "fail " + e.javaClass.simpleName + " elapsedMs=" + (SystemClock.elapsedRealtime() - started))
                toast(MSG_NO_CONNECTION)
                SendOutcome.Failed
            } finally {
                Arrays.fill(wav, 0)
            }
            sending = false
            sendJob = null
            when (outcome) {
                is SendOutcome.Done -> {
                    val resp = outcome.response
                    when {
                        outcome.code != 200 || resp == null ->
                            toast(MSG_BAD_RECORDING)
                        resp.action == null ->
                            toast(MSG_NOTHING_TO_CHANGE)
                        resp.action.action == "insert" -> applyInsert(resp)
                        resp.action.action == "rewrite" -> applyRewrite(resp)
                        else -> toast(MSG_REPLACE_UNSUPPORTED)
                    }
                }
                SendOutcome.Failed -> toast(MSG_NO_CONNECTION)
            }
            // A newer recording owns the pill; don't clobber it.
            if (!recording) keyboardView?.showIdleBar()
        }
    }

    private fun applyInsert(resp: ProcessResponse) {
        val ed = editor ?: return
        val action = resp.action ?: return
        val inputType = currentInputEditorInfo?.inputType ?: EditorInfo.TYPE_NULL
        val prev = ed.readFullText(inputType, ContextPolicy.CONTEXT_MAX_CHARS).full
        ed.commitText(action.text)
        showUndo(prev)
        if (resp.usedFallback) toast(MSG_INSERTED_FALLBACK) else toast(MSG_INSERTED)
    }

    private fun applyRewrite(resp: ProcessResponse) {
        val ed = editor ?: return
        val action = resp.action ?: return
        val inputType = currentInputEditorInfo?.inputType ?: EditorInfo.TYPE_NULL
        val current = ed.readFullText(inputType, ContextPolicy.CONTEXT_MAX_CHARS)
        if (!current.reliable) {
            toast(MSG_SELECTION_UNSURE)
            return
        }
        if (ActionApplier.isTooLong(current.full)) {
            toast(MSG_TOO_LONG)
            return
        }
        if (current.full != snapshotFull) {
            toast(MSG_TEXT_CHANGED)
            return
        }
        when (ActionApplier.applyAction(current.full, action).outcome) {
            ActionApplier.Outcome.NOTHING_CHANGED -> toast(MSG_NOTHING_CHANGED)
            ActionApplier.Outcome.TOO_LONG -> toast(MSG_TOO_LONG)
            ActionApplier.Outcome.REPLACE_UNSUPPORTED -> toast(MSG_REPLACE_UNSUPPORTED)
            ActionApplier.Outcome.NULL_ACTION -> toast(MSG_NOTHING_TO_CHANGE)
            ActionApplier.Outcome.REWRITTEN -> {
                if (current.selected.isNotEmpty() && !ed.collapseSelectionTo(current.endCharIndex)) {
                    toast(MSG_SELECTION_UNSURE)
                    return
                }
                val beforeCp = ed.codePointCount(current.before + current.selected)
                val afterCp = ed.codePointCount(current.after)
                val prev = current.full
                if (!ed.rewriteFull(beforeCp, afterCp, action.text)) {
                    toast(MSG_SELECTION_UNSURE)
                    return
                }
                showUndo(prev)
                toast(MSG_REWRITTEN)
            }
            ActionApplier.Outcome.INSERTED -> {
                // Unreachable: insert is routed to applyInsert. Kept for exhaustiveness.
            }
        }
    }

    private fun cancelSend() {
        backend?.cancel()
        sendJob?.cancel()
        sendJob = null
        sending = false
    }

    private fun store(): SettingsStore =
        settings ?: SettingsStore(this).also { settings = it }

    private fun openSetup() {
        startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    private fun toast(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
    }

    private fun hasMicPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED

    private sealed interface SendOutcome {
        data object Failed : SendOutcome
        data class Done(val code: Int, val response: ProcessResponse?) : SendOutcome
    }

    companion object {
        private const val TAG = "VBOARD_NET"
        private const val MSG_NO_CONNECTION = "No connection. Try again."
        private const val MSG_BAD_RECORDING = "Couldn't use that recording. Try again."
        private const val MSG_INSERTED = "Inserted"
        private const val MSG_INSERTED_FALLBACK = "Inserted from transcript."
        private const val MSG_REWRITTEN = "Rewritten"
        private const val MSG_NOTHING_CHANGED = "Nothing changed"
        private const val MSG_NOTHING_TO_CHANGE = "Nothing to change"
        private const val MSG_REPLACE_UNSUPPORTED = "That edit isn't supported yet"
        private const val MSG_TOO_LONG = "Text too long to edit"
        private const val MSG_TEXT_CHANGED = "Text changed. Kept current text."
        private const val MSG_SELECTION_UNSURE = "Couldn't replace selected text. Kept current text."
    }
}
