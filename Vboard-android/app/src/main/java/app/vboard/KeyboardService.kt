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
import app.vboard.suggest.SuggestionController
import app.vboard.voice.StreamMessages
import app.vboard.voice.VoiceStreamRunner
import java.util.Arrays
import kotlin.coroutines.cancellation.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class KeyboardService : InputMethodService(), KeyboardView.Listener, TopBarView.Listener, MinimizeModeView.Listener {

    private var keyboardView: KeyboardView? = null
    private var editor: TextBoxEditor? = null
    private var imeOptions: Int = EditorInfo.IME_NULL
    private var recorder: Recorder? = null
    private var recording = false

    /** Minimize mode: keys and top bar hide, only the pill shows and is touchable. */
    private var minimized = false

    /** Pill direction; persisted, restored with the mode and position. */
    private var smallOrientation = MinimizePolicy.Orientation.VERTICAL

    /** Take confirmed with ✓, held in RAM until the send finishes. Zeroed after. */
    private var pendingWav: ByteArray? = null

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var settings: SettingsStore? = null
    private var backend: BackendClient? = null
    private var lastBackendUrl: String? = null
    private var sendJob: Job? = null

    /** WS stream for the current utterance; null when streaming is off/unavailable. */
    private var streamRunner: VoiceStreamRunner? = null

    /** Full box text at ✓, kept for the POST fallback when the stream fails. */
    private var pendingContextText = ""

    /** True while a /v1/process round-trip is in flight; a second ✓ is ignored. */
    private var sending = false

    /** One-level Undo: full box text saved before an AI insert/rewrite. */
    private var undoText: String? = null

    /** English word suggestions; loads words_en.txt lazily, survives view recreates. */
    private var suggestController: SuggestionController? = null

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
            it.minimizeListener = this
            val controller = suggestController ?: SuggestionController(
                scope = serviceScope,
                openWordList = {
                    try {
                        assets.open("words_en.txt")
                    } catch (_: Exception) {
                        null
                    }
                },
                onSuggestions = { words ->
                    if (words.isEmpty()) keyboardView?.clearSuggestions()
                    else keyboardView?.showSuggestions(words)
                },
            ).also { created -> suggestController = created }
            it.setOnSuggestionPick { word -> pickSuggestion(word) }
            controller.start()
            keyboardView = it
        }
    }

    override fun onStartInputView(info: EditorInfo?, restarting: Boolean) {
        super.onStartInputView(info, restarting)
        imeOptions = info?.imeOptions ?: EditorInfo.IME_NULL
        clearUndo()
        keyboardView?.showLetters()
        keyboardView?.refreshInsets()
        if (!restarting) maybeAutoCapitalize()
        updateSuggestions()
        if (store().isMinimized() && !minimized) enterMinimize()
    }

    /**
     * Minimize mode: only the pill is touchable and the app keeps its full
     * height behind the keyboard, so it is not pushed up and stays usable.
     */
    override fun onComputeInsets(outInsets: InputMethodService.Insets) {
        super.onComputeInsets(outInsets)
        if (!minimized) return
        val fullHeight = resources.displayMetrics.heightPixels
        outInsets.contentTopInsets = fullHeight
        outInsets.visibleTopInsets = fullHeight
        outInsets.touchableInsets = InputMethodService.Insets.TOUCHABLE_INSETS_REGION
        outInsets.touchableRegion.setEmpty()
        keyboardView?.minimizeTouchableRect()?.let { outInsets.touchableRegion.set(it) }
    }

    override fun onFinishInputView(finishingInput: Boolean) {
        super.onFinishInputView(finishingInput)
        keyboardView?.cancelKeyRepeats()
        keyboardView?.resetShift()
        keyboardView?.showLetters()
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
        suggestController = null
        super.onDestroy()
    }

    /**
     * Cursor moves (tap-to-move) re-query the strip; a new selection hides
     * it via readWordBeforeCursor. Never changes text, so no loops.
     */
    override fun onUpdateSelection(
        oldSelStart: Int,
        oldSelEnd: Int,
        newSelStart: Int,
        newSelEnd: Int,
        candidatesStart: Int,
        candidatesEnd: Int,
    ) {
        super.onUpdateSelection(oldSelStart, oldSelEnd, newSelStart, newSelEnd, candidatesStart, candidatesEnd)
        updateSuggestions()
    }

    override fun onText(text: String) {
        clearUndo()
        editor?.commitText(text)
        // Gboard-like: typing space after ". " arms one-shot shift.
        if (text == " ") maybeAutoCapitalize()
        updateSuggestions()
    }

    override fun onBackspace() {
        keyboardView?.clearOneShotShift()
        deleteBackwards()
        updateSuggestions()
    }

    override fun onBackspaceRepeat(): Boolean {
        val ed = editor ?: return false
        val keepGoing = KeyLayouts.RepeatTiming.shouldContinue(ed.hasTextBeforeCursor())
        if (keepGoing) {
            deleteBackwards()
            updateSuggestions()
        }
        return keepGoing
    }

    override fun onEnter() {
        clearUndo()
        val inputType = currentInputEditorInfo?.inputType ?: EditorInfo.TYPE_NULL
        editor?.performEnter(inputType, imeOptions)
        // Fresh line after Enter reads as a sentence start.
        maybeAutoCapitalize()
        updateSuggestions()
    }

    override fun onShiftChanged(capsLock: Boolean) = Unit

    override fun onGlobe() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            switchToNextInputMethod(false)
        }
    }

    override fun onSymbolsToggle() {
        keyboardView?.toggleSymbols()
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
        // Stream-first: connect now so mic slices flow live; when the socket
        // never opens the take still records and POSTs at ✓.
        val runner = prepareStream()
        val rec = Recorder(
            onAmplitude = { raw -> keyboardView?.post { keyboardView?.setRecordingAmplitude(raw) } },
            onAutoStop = { keyboardView?.post { finishRecording(auto = true) } },
            onChunk = { chunk -> runner?.offerPcm(chunk) },
        )
        when (rec.start()) {
            Recorder.StartResult.Started -> {
                recorder = rec
                recording = true
                streamRunner = runner
                keyboardView?.showRecordingBar()
            }
            Recorder.StartResult.Failed -> {
                runner?.cancel()
                Toast.makeText(this, "Microphone unavailable. Try again.", Toast.LENGTH_SHORT).show()
            }
        }
    }

    override fun onAiClick() {
        if (sending || recording) return
        val ed = editor ?: return
        val inputType = currentInputEditorInfo?.inputType ?: EditorInfo.TYPE_NULL
        if (ContextPolicy.isPasswordInputType(inputType)) return
        val current = ed.readFullText(inputType, ContextPolicy.CONTEXT_MAX_CHARS)
        if (!current.reliable) {
            toast(MSG_SELECTION_UNSURE)
            return
        }
        val full = current.full
        if (full.isEmpty()) {
            toast(MSG_NOTHING_TO_CLEAN)
            return
        }
        if (ActionApplier.isTooLong(full)) {
            toast(MSG_TOO_LONG)
            return
        }
        snapshotFull = full
        keyboardView?.showAgentWorkingBar()
        sendAgentToBackend(store(), full)
    }

    override fun onCancel() {
        if (!recording) return
        stopRecordingSilently()
        cancelStream()
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

    override fun onMinimizeClick() {
        enterMinimize()
    }

    /**
     * Pill mic lives only in the idle face: start recording and show the
     * recording face. Same guards, Recorder and stream-first path as voice.
     */
    override fun onMicClick() {
        if (recording) return
        onVoiceClick()
    }

    /** Pill check: stop, send through the unchanged voice path, stay small. */
    override fun onCheckClick() {
        if (!minimized || !recording) return
        finishRecording(auto = false)
    }

    /** Pill X: cancels the recording only; idle it is not shown. */
    override fun onCancelClick() = onCancel()

    /** Pill delete: selected text goes whole, otherwise one code point back. */
    override fun onDeleteClick() = deleteBackwards()

    /**
     * Backspace for the pill: holding repeats (the view re-fires), and an
     * active selection deletes whole via an empty commit. Password fields
     * delete blindly, exactly like the keyboard key — never read there.
     */
    private fun deleteBackwards() {
        val ed = editor ?: return
        val inputType = currentInputEditorInfo?.inputType ?: EditorInfo.TYPE_NULL
        clearUndo()
        if (!ContextPolicy.isPasswordInputType(inputType)) {
            val selected = try {
                currentInputConnection?.getSelectedText(0)?.toString()
            } catch (_: Exception) {
                null
            }
            if (!selected.isNullOrEmpty()) {
                ed.commitText("")
                return
            }
        }
        ed.deleteCodePointBefore()
    }

    /**
     * Keyboard button cycles: vertical idle flips to horizontal, horizontal
     * idle returns to the full keyboard. The flip key is gone on purpose.
     */
    override fun onKeyboardClick() {
        if (!minimized) return
        if (smallOrientation == MinimizePolicy.Orientation.VERTICAL) {
            smallOrientation = MinimizePolicy.flipped(smallOrientation)
            store().setMinimizeOrientation(smallOrientation)
            keyboardView?.setMinimizeOrientation(smallOrientation)
        } else {
            smallOrientation = MinimizePolicy.Orientation.VERTICAL
            store().setMinimizeOrientation(smallOrientation)
            exitMinimize()
        }
    }

    override fun onPillDragged(dxPx: Int, dyPx: Int) {
        if (!minimized) return
        keyboardView?.moveMinimizeBy(dxPx, dyPx)
    }

    override fun onPillDragEnd() {
        if (!minimized) return
        val pos = keyboardView?.minimizePosition() ?: return
        if (pos.first >= 0 && pos.second >= 0) store().setMinimizePosition(pos.first, pos.second)
    }

    /**
     * Minimize mode: keys and top bar hide, only the pill shows. Blocked
     * mid-flight; the pill owns no send state. Mode persists in SettingsStore.
     */
    private fun enterMinimize() {
        if (minimized || !MinimizePolicy.canEnter(recording, sending)) return
        minimized = true
        store().setMinimized(true)
        keyboardView?.showMinimized()
        smallOrientation = store().getMinimizeOrientation()
        keyboardView?.setMinimizeOrientation(smallOrientation)
        val pos = store().getMinimizePosition()
        if (pos != null) keyboardView?.setMinimizePosition(pos.first, pos.second)
        else keyboardView?.defaultMinimizePosition()
    }

    private fun exitMinimize() {
        if (!minimized) return
        minimized = false
        store().setMinimized(false)
        keyboardView?.showFullKeyboard()
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
            // Short take: nothing to stream or POST.
            cancelStream()
            keyboardView?.showIdleBar()
            if (!auto) Toast.makeText(this, "Too short. Hold the thought a beat longer.", Toast.LENGTH_SHORT).show()
            return
        }
        pendingWav = wav
        val store = store()
        if (!store.hasLanguages()) {
            cancelStream()
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
            cancelStream()
            clearPendingWav()
            keyboardView?.showIdleBar()
            toast(MSG_SELECTION_UNSURE)
            return
        }
        snapshotFull = full.full
        val contextText = capContextText(full)
        keyboardView?.showProcessingBar()
        pendingContextText = contextText
        val runner = streamRunner
        streamRunner = null
        if (runner != null && runner.finish()) {
            // Stream path: the final/fallback arrives via the runner events.
            sending = true
        } else {
            // No live socket (never opened, or failed mid-record): the
            // single POST retry path doubles as the plain fallback.
            runner?.cancel()
            sendToBackend(store, contextText)
        }
    }

    /**
     * Connects the WS stream at record start so mic slices flow live. The
     * `start` frame mirrors POST /v1/process: same `device_id`, same
     * `languages` CSV, same capped box text (`box_text`), plus the source
     * app package (`app`). Null when the URL is unusable — recording still
     * proceeds and POSTs at ✓. Never throws.
     */
    private fun prepareStream(): VoiceStreamRunner? {
        return try {
            val store = store()
            val baseUrl = store.getBackendUrl()
            if (StreamMessages.toWebSocketUrl(baseUrl) == null) return null
            val inputType = currentInputEditorInfo?.inputType ?: EditorInfo.TYPE_NULL
            val full = editor?.readFullText(inputType, ContextPolicy.CONTEXT_MAX_CHARS)
            val boxText = if (full != null && full.reliable) capContextText(full) else ""
            val appName = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                try {
                    currentInputEditorInfo?.packageName
                } catch (_: Exception) {
                    null
                }
            } else {
                null
            }
            val startJson = StreamMessages.buildStart(
                deviceId = store.getDeviceId(),
                languages = store.getLanguagesCsv(),
                boxText = boxText,
                app = appName,
            )
            val runner = VoiceStreamRunner(
                serviceScope,
                object : VoiceStreamRunner.Events {
                    override fun onStreamFinal(final: StreamMessages.ServerMessage.Final) {
                        handleStreamFinal(final)
                    }

                    override fun onStreamFallback(reason: String) {
                        handleStreamFallback(reason)
                    }
                },
            )
            if (runner.start(baseUrl, startJson)) runner else null
        } catch (_: Exception) {
            null
        }
    }

    /** Tears down the WS stream without firing events. Callers own the UI. */
    private fun cancelStream() {
        val runner = streamRunner
        streamRunner = null
        try {
            runner?.cancel()
        } catch (_: Exception) {
            // Teardown must never crash the IME.
        }
    }

    /**
     * Stream `final`: identical handling to the POST path — the action is
     * applied, never the interim text. Numbers only in the log.
     */
    private fun handleStreamFinal(final: StreamMessages.ServerMessage.Final) {
        serviceScope.launch {
            sending = false
            sendJob = null
            Log.d(TAG, "stream final usedFallback=" + final.usedFallback + " cut=" + final.cut)
            applyProcessResult(
                200,
                ProcessResponse(
                    transcript = final.transcript,
                    action = final.action,
                    usedFallback = final.usedFallback,
                    note = final.note,
                ),
            )
            clearPendingWav()
            // A newer recording owns the pill; don't clobber it.
            if (!recording) keyboardView?.showIdleBar()
        }
    }

    /**
     * Any stream failure: the single POST /v1/process retry with the
     * retained WAV. Reason is a code (never content). While still recording
     * the ✓-time `finish()` takes the POST path instead, so this is a no-op.
     */
    private fun handleStreamFallback(reason: String) {
        serviceScope.launch {
            if (recording) return@launch
            Log.d(TAG, "stream fallback reason=" + reason)
            sending = false
            sendJob = null
            if (pendingWav == null) {
                keyboardView?.showIdleBar()
                return@launch
            }
            sendToBackend(store(), pendingContextText)
        }
    }

    /** Wire-length box text, capped nearest-the-cursor-first. */
    private fun capContextText(full: TextBoxEditor.FullText): String {
        return if (full.full.length <= ContextPolicy.CONTEXT_MAX_CHARS) {
            full.full
        } else {
            ContextPolicy.capContext(full.before + full.selected, full.after, ContextPolicy.CONTEXT_MAX_CHARS)
        }
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
        pendingContextText = ""
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
                is SendOutcome.Done -> applyProcessResult(outcome.code, outcome.response)
                SendOutcome.Failed -> toast(MSG_NO_CONNECTION)
            }
            // A newer recording owns the pill; don't clobber it.
            if (!recording) keyboardView?.showIdleBar()
        }
    }

    /**
     * Shared result handling for the POST path and the stream `final` path:
     * insert/rewrite apply, null action or errors toast. Partial text never
     * reaches here.
     */
    private fun applyProcessResult(code: Int, resp: ProcessResponse?) {
        when {
            code != 200 || resp == null ->
                toast(MSG_BAD_RECORDING)
            resp.action == null ->
                toast(MSG_NOTHING_TO_CHANGE)
            resp.action.action == "insert" -> applyInsert(resp)
            resp.action.action == "rewrite" -> applyRewrite(resp)
            else -> toast(MSG_REPLACE_UNSUPPORTED)
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
        cancelStream()
        backend?.cancel()
        sendJob?.cancel()
        sendJob = null
        sending = false
    }

    private fun sendAgentToBackend(store: SettingsStore, content: String) {
        if (sending) return
        sending = true
        val url = store.getBackendUrl()
        if (backend == null || lastBackendUrl != url) {
            backend = BackendClient(url)
            lastBackendUrl = url
        }
        val client = backend
        if (client == null) {
            sending = false
            keyboardView?.showIdleBar()
            return
        }
        val deviceId = store.getDeviceId()
        // TEMPORARY debug: numbers only, never user text.
        Log.d(TAG, "agent send chars=" + content.length + " host=" + Uri.parse(url).host)
        sendJob?.cancel()
        sendJob = serviceScope.launch {
            val started = SystemClock.elapsedRealtime()
            val outcome: AgentOutcome = try {
                val res = withContext(Dispatchers.IO) {
                    client.agent(content, deviceId)
                }
                Log.d(TAG, "agent got status=" + res.httpCode + " elapsedMs=" + (SystemClock.elapsedRealtime() - started))
                if (res.httpCode == 422) {
                    AgentOutcome.Done(res.httpCode, null, AgentResponseParser.parseErrorDetail(res.body))
                } else {
                    AgentOutcome.Done(res.httpCode, AgentResponseParser.parse(res.body), null)
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.d(TAG, "agent fail " + e.javaClass.simpleName + " elapsedMs=" + (SystemClock.elapsedRealtime() - started))
                AgentOutcome.Failed
            }
            sending = false
            sendJob = null
            when (outcome) {
                is AgentOutcome.Done -> {
                    when {
                        outcome.code == 422 -> toast(outcome.errorDetail ?: MSG_AGENT_FAILED)
                        outcome.code != 200 || outcome.response == null -> toast(MSG_AGENT_FAILED)
                        outcome.response.text.isEmpty() -> toast(MSG_AGENT_FAILED)
                        else -> applyAgentRewrite(outcome.response.text)
                    }
                }
                AgentOutcome.Failed -> toast(MSG_NO_CONNECTION)
            }
            // A newer recording owns the pill; don't clobber it.
            if (!recording) keyboardView?.showIdleBar()
        }
    }

    private fun applyAgentRewrite(newText: String) {
        val ed = editor ?: return
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
        if (current.full == newText) {
            toast(MSG_NOTHING_CHANGED)
            return
        }
        if (current.selected.isNotEmpty() && !ed.collapseSelectionTo(current.endCharIndex)) {
            toast(MSG_SELECTION_UNSURE)
            return
        }
        val beforeCp = ed.codePointCount(current.before + current.selected)
        val afterCp = ed.codePointCount(current.after)
        val prev = current.full
        if (!ed.rewriteFull(beforeCp, afterCp, newText)) {
            toast(MSG_SELECTION_UNSURE)
            return
        }
        showUndo(prev)
        toast(MSG_REWRITTEN)
    }

    /**
     * Refresh the strip after a commit or cursor move. The commit already
     * returned, so typing never waits on this; the strip hides for
     * password fields, unreadable boxes, selections, and non-idle states.
     */
    private fun updateSuggestions() {
        val controller = suggestController ?: return
        if (recording || sending) {
            controller.hide()
            return
        }
        val inputType = currentInputEditorInfo?.inputType ?: EditorInfo.TYPE_NULL
        if (ContextPolicy.isPasswordInputType(inputType)) {
            controller.hide()
            return
        }
        controller.onCommitted(editor?.readWordBeforeCursor(), password = false, idle = true)
    }

    /** Strip tap: swap the current word for the pick, keep initial caps. */
    private fun pickSuggestion(word: String) {
        if (recording || sending) return
        val ed = editor ?: return
        val inputType = currentInputEditorInfo?.inputType ?: EditorInfo.TYPE_NULL
        if (ContextPolicy.isPasswordInputType(inputType)) return
        val current = ed.readWordBeforeCursor() ?: return
        if (current.isEmpty()) return
        val controller = suggestController ?: return
        clearUndo()
        if (ed.replaceTrailingWord(current.length, controller.buildReplacement(current, word))) {
            updateSuggestions()
        }
    }

    private fun store(): SettingsStore =
        settings ?: SettingsStore(this).also { settings = it }

    /**
     * Gboard-like auto-caps: arms one-shot shift at a sentence start
     * (empty box, fresh line, or after ". "). Reads only a short tail
     * before the cursor; skips password fields and selections; numbers
     * only, never logged by this file's conventions.
     */
    private fun maybeAutoCapitalize() {
        val ed = editor ?: return
        val kv = keyboardView ?: return
        val inputType = currentInputEditorInfo?.inputType ?: EditorInfo.TYPE_NULL
        if (ContextPolicy.isPasswordInputType(inputType)) return
        val cur = ed.readFullText(inputType, AUTOCAPS_LOOKBACK)
        if (!cur.reliable || cur.selected.isNotEmpty()) return
        if (KeyLayouts.sentenceNeedsCaps(cur.before)) kv.setShiftSingle()
    }

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

    private sealed interface AgentOutcome {
        data object Failed : AgentOutcome
        data class Done(val code: Int, val response: AgentResponse?, val errorDetail: String?) : AgentOutcome
    }

    companion object {
        private const val TAG = "VBOARD_NET"
        /** Chars of lookback for auto-caps; a sentence boundary needs far less. */
        private const val AUTOCAPS_LOOKBACK = 16
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
        private const val MSG_NOTHING_TO_CLEAN = "Nothing to clean up"
        private const val MSG_AGENT_FAILED = "Couldn't clean up. Try again."
    }
}
