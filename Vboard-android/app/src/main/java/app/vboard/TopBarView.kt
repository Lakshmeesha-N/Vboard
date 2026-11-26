package app.vboard

import android.content.Context
import android.graphics.drawable.Drawable
import android.os.SystemClock
import android.util.AttributeSet
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.widget.AppCompatImageButton
import androidx.core.content.ContextCompat
import app.vboard.suggest.SuggestionStripView

class TopBarView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0,
) : LinearLayout(context, attrs, defStyleAttr) {

    interface Listener {
        fun onVoiceClick()
        fun onAiClick()
        fun onCancel()
        fun onConfirm()
        fun onUndo()
        fun onMinimizeClick()
    }

    var listener: Listener? = null

    private val idleRow: LinearLayout
    private val pill: LinearLayout
    private val agentRow: LinearLayout
    private val wave: WaveformView
    private val timerText: TextView
    private var undoButton: TextView? = null
    private var cancelButton: TextView? = null
    private var confirmButton: TextView? = null
    private var recordStartMs = 0L
    private lateinit var strip: SuggestionStripView
    private var toolsOpen = false
    private var gridButton: AppCompatImageButton? = null
    private var backButton: AppCompatImageButton? = null
    private var toolsRow: LinearLayout? = null
    private var middleSpacer: android.view.View? = null

    private val timerTick = object : Runnable {
        override fun run() {
            val seconds = ((SystemClock.elapsedRealtime() - recordStartMs) / 1000).toInt().coerceAtLeast(0)
            timerText.text = "%d:%02d".format(seconds / 60, seconds % 60)
            timerText.postDelayed(this, TIMER_INTERVAL_MS)
        }
    }

    init {
        orientation = VERTICAL
        gravity = Gravity.CENTER_VERTICAL
        setPadding(0, dp(2), dp(2), dp(2))

        idleRow = LinearLayout(context).apply {
            orientation = HORIZONTAL
            gravity = Gravity.END or Gravity.CENTER_VERTICAL
            layoutParams = LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT)
        }
        // Far-left tools toggle (plain grid, no glow): tap swaps the
        // suggestion strip for the tools row; back arrow restores it.
        // Voice / Undo / AI on the right stay unchanged.
        gridButton = makeButton(
            "More tools",
            R.drawable.topbar_button_background,
            GridIconDrawable(context),
            TOGGLE_BUTTON_DP,
        ) {
            setToolsOpen(true)
        }.also { idleRow.addView(it) }
        backButton = makeButton(
            "Back to suggestions",
            R.drawable.topbar_button_background,
            BackArrowDrawable(context),
            TOGGLE_BUTTON_DP,
        ) {
            setToolsOpen(false)
        }.also {
            it.visibility = GONE
            idleRow.addView(it)
        }
        toolsRow = LinearLayout(context).apply {
            orientation = HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            visibility = GONE
            isFocusable = false
            // Dimmed until Clipboard / Small mode are built (later steps).
            alpha = TOOLS_DIM_ALPHA
            layoutParams = LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f)
        }
        val row = toolsRow
        if (row != null) {
            row.addView(makeToolChip("Clipboard", ClipboardIconDrawable(context), first = true))
            row.addView(
                makeToolChip(
                    "Minimize",
                    SmallModeIconDrawable(context),
                    first = false,
                    enabled = true,
                    onDown = { listener?.onMinimizeClick() },
                )
            )
        }
        idleRow.addView(toolsRow)
        strip = SuggestionStripView(context).apply {
            layoutParams = LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f)
        }
        idleRow.addView(strip)
        // Fallback filler: the strip is GONE when empty, and without this the
        // right-gravity row would pull the toggle off the far left. Fixed 1dp
        // height: a bare View with WRAP_CONTENT measures to the full parent
        // height and stretches the whole bar, pushing the keys off-screen.
        middleSpacer = android.view.View(context).apply {
            visibility = GONE
            isFocusable = false
            layoutParams = LayoutParams(0, dp(1), 1f)
        }
        idleRow.addView(middleSpacer)
        idleRow.addView(
            makeButton(
                "Voice input",
                R.drawable.topbar_button_background,
                VoiceBarsDrawable(context),
                VOICE_BUTTON_DP,
            ) {
                listener?.onVoiceClick()
            }
        )
        undoButton = makeTextButton("Undo", "↩", 0xFFFFFFFF.toInt(), transparent = true) {
            listener?.onUndo()
        }.also {
            it.visibility = GONE
            idleRow.addView(it)
        }
        idleRow.addView(
            makeButton(
                "AI actions",
                R.drawable.ai_ring_background,
                null,
                AI_BUTTON_DP,
            ) {
                listener?.onAiClick()
            }
        )
        addView(idleRow)

        pill = LinearLayout(context).apply {
            orientation = HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            background = ContextCompat.getDrawable(context, R.drawable.recording_pill_background)
            val pad = dp(6)
            setPadding(pad, dp(4), pad, dp(4))
            layoutParams = LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT)
            visibility = GONE
        }
        wave = WaveformView(context).apply {
            layoutParams = LayoutParams(0, dp(WAVE_HEIGHT_DP), WAVE_WIDTH_WEIGHT)
        }
        timerText = TextView(context).apply {
            contentDescription = "Recording time"
            setTextColor(0xFF9AA0A6.toInt())
            textSize = 13f
            typeface = android.graphics.Typeface.MONOSPACE
            gravity = Gravity.CENTER_VERTICAL
            isFocusable = false
            layoutParams = LayoutParams(
                LayoutParams.WRAP_CONTENT,
                LayoutParams.MATCH_PARENT,
            ).apply { marginStart = dp(GAP_DP) }
        }
        pill.addView(timerText)
        pill.addView(android.view.View(context).apply {
            layoutParams = LayoutParams(0, 1, WAVE_SPACER_WEIGHT)
            isFocusable = false
        })
        pill.addView(wave)
        cancelButton = makeTextButton("Cancel recording", "✕", 0xFF9AA0A6.toInt(), transparent = true) {
            listener?.onCancel()
        }.also { pill.addView(it) }
        confirmButton = makeTextButton("Send recording", "✓", 0xFF1E2025.toInt(), transparent = false) {
            listener?.onConfirm()
        }.also { pill.addView(it) }
        addView(pill)

        // Agent round-trip status: deliberately NOT the recording pill (no wave,
        // no ✕/✓) so a ring tap can never look like recording started.
        agentRow = LinearLayout(context).apply {
            orientation = HORIZONTAL
            gravity = Gravity.CENTER
            background = ContextCompat.getDrawable(context, R.drawable.recording_pill_background)
            val pad = dp(6)
            setPadding(pad, dp(8), pad, dp(8))
            layoutParams = LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT)
            visibility = GONE
            isFocusable = false
        }
        agentRow.addView(TextView(context).apply {
            text = "Working..."
            setTextColor(0xFF9AA0A6.toInt())
            textSize = 13f
            gravity = Gravity.CENTER
            isFocusable = false
        })
        addView(agentRow)
    }

    fun showIdle() {
        setToolsOpen(false)
        idleRow.visibility = VISIBLE
        pill.visibility = GONE
        agentRow.visibility = GONE
        strip.clear()
        syncMiddle()
        stopTimer()
        setPillEnabled(true)
        wave.reset()
    }

    fun showRecording() {
        idleRow.visibility = GONE
        agentRow.visibility = GONE
        pill.visibility = VISIBLE
        strip.clear()
        setPillEnabled(true)
        wave.reset()
        startTimer()
    }

    fun showProcessing() {
        idleRow.visibility = GONE
        agentRow.visibility = GONE
        pill.visibility = VISIBLE
        strip.clear()
        stopTimer()
        setPillEnabled(false)
    }

    /** Agent round-trip: status row only. Never touches the recording pill. */
    fun showAgentWorking() {
        idleRow.visibility = GONE
        pill.visibility = GONE
        strip.clear()
        stopTimer()
        wave.reset()
        agentRow.visibility = VISIBLE
    }

    /** Undo is visible only in the idle bar, after an AI edit. */
    fun setUndoVisible(visible: Boolean) {
        undoButton?.visibility = if (visible) VISIBLE else GONE
    }

    /** Tools row replaces ONLY the suggestion strip; keys are untouched. */
    private fun setToolsOpen(open: Boolean) {
        toolsOpen = open
        gridButton?.visibility = if (open) GONE else VISIBLE
        backButton?.visibility = if (open) VISIBLE else GONE
        toolsRow?.visibility = if (open) VISIBLE else GONE
        if (open) strip.clear()
        syncMiddle()
    }

    /**
     * Exactly one middle filler is visible: the tools row, the strip, or the
     * fallback spacer. Keeps the toggle pinned far left and Voice/AI right.
     */
    private fun syncMiddle() {
        middleSpacer?.visibility =
            if (!toolsOpen && strip.visibility != VISIBLE) VISIBLE else GONE
    }

    /** Rounded gray chip with icon + label, button height. Dimmed until built. */
    private fun makeToolChip(
        description: String,
        icon: Drawable,
        first: Boolean,
        enabled: Boolean = false,
        onDown: (() -> Unit)? = null,
    ): LinearLayout {
        return LinearLayout(context).apply {
            orientation = HORIZONTAL
            gravity = Gravity.CENTER
            contentDescription = description
            background = ContextCompat.getDrawable(context, R.drawable.tools_chip_background)
            isFocusable = false
            isEnabled = enabled
            layoutParams = LayoutParams(0, dp(BUTTON_DP), 1f).apply {
                if (!first) marginStart = dp(GAP_DP)
            }
            addView(ImageView(context).apply {
                setImageDrawable(icon)
                scaleType = ImageView.ScaleType.CENTER
                isFocusable = false
                isEnabled = enabled
                layoutParams = LayoutParams(dp(TOOL_ICON_DP), dp(TOOL_ICON_DP))
            })
            addView(TextView(context).apply {
                text = description
                setTextColor(0xFFFFFFFF.toInt())
                setTextSize(
                    android.util.TypedValue.COMPLEX_UNIT_SP,
                    TOOLS_TEXT_SP,
                )
                gravity = Gravity.CENTER_VERTICAL
                maxLines = 1
                isSingleLine = true
                ellipsize = android.text.TextUtils.TruncateAt.END
                isFocusable = false
                isEnabled = enabled
                layoutParams = LayoutParams(
                    LayoutParams.WRAP_CONTENT,
                    LayoutParams.WRAP_CONTENT,
                ).apply { marginStart = dp(TOOL_LABEL_GAP_DP) }
            })
            if (onDown != null) setDownHaptic(onDown)
        }
    }

    /** Shows word suggestions in the idle strip; no-op when empty or tools open. */
    fun showSuggestions(words: List<String>) {
        if (toolsOpen) return
        strip.setSuggestions(words)
        syncMiddle()
    }

    fun clearSuggestions() {
        strip.clear()
        syncMiddle()
    }

    fun setOnSuggestionPick(onPick: ((String) -> Unit)?) {
        strip.onPick = onPick
    }

    override fun onDetachedFromWindow() {
        stopTimer()
        super.onDetachedFromWindow()
    }

    private fun startTimer() {
        recordStartMs = SystemClock.elapsedRealtime()
        timerText.removeCallbacks(timerTick)
        timerText.post(timerTick)
    }

    private fun stopTimer() {
        timerText.removeCallbacks(timerTick)
    }

    fun setAmplitude(raw: Float) {
        if (pill.visibility == VISIBLE) wave.setRawAmplitude(raw)
    }

    private fun setPillEnabled(enabled: Boolean) {
        cancelButton?.isEnabled = enabled
        confirmButton?.isEnabled = enabled
        pill.alpha = if (enabled) 1f else 0.5f
    }

    private fun makeButton(
        description: String,
        backgroundRes: Int,
        icon: Drawable?,
        buttonDp: Int = BUTTON_DP,
        onDown: () -> Unit,
    ): AppCompatImageButton {
        return AppCompatImageButton(context).apply {
            contentDescription = description
            background = ContextCompat.getDrawable(context, backgroundRes)
            if (icon != null) setImageDrawable(icon)
            scaleType = ImageView.ScaleType.CENTER
            isFocusable = false
            isClickable = true
            val size = dp(buttonDp)
            layoutParams = LayoutParams(size, size).apply {
                marginStart = dp(GAP_DP)
            }
            setDownHaptic(onDown)
        }
    }

    private fun makeTextButton(
        description: String,
        label: String,
        textColor: Int,
        transparent: Boolean,
        buttonDp: Int = BUTTON_DP,
        onDown: () -> Unit,
    ): TextView {
        return TextView(context).apply {
            contentDescription = description
            text = label
            setTextColor(textColor)
            textSize = 20f
            gravity = Gravity.CENTER
            isFocusable = false
            isClickable = true
            background = if (transparent) {
                null
            } else {
                ContextCompat.getDrawable(context, R.drawable.confirm_button_background)
            }
            val size = dp(BUTTON_DP)
            layoutParams = LayoutParams(size, size).apply {
                marginStart = dp(GAP_DP)
            }
            setDownHaptic(onDown)
        }
    }

    private fun arm(view: android.view.View, onDown: () -> Unit) {
        view.setOnTouchListener { touched, event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    if (!touched.isEnabled) return@setOnTouchListener false
                    touched.isPressed = true
                    touched.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                    onDown()
                    true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    touched.isPressed = false
                    if (event.actionMasked == MotionEvent.ACTION_UP) touched.performClick()
                    true
                }
                else -> false
            }
        }
    }

    private fun android.view.View.setDownHaptic(onDown: () -> Unit) =
        arm(this, onDown)

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    companion object {
        private const val BUTTON_DP = 40
        /** Voice record button: layout, draw and touch, all 42dp. */
        private const val VOICE_BUTTON_DP = 42
        /** Tools toggle (grid / back arrow): 70% of the voice button. */
        private const val TOGGLE_BUTTON_DP = 29
        /** Cleanup (AI) button: 2dp smaller than stock, voice untouched. */
        private const val AI_BUTTON_DP = 38
        private const val GAP_DP = 8
        private const val WAVE_HEIGHT_DP = 40

        /** Wave takes ~40% of the pill's free width, right-aligned by the spacer. */
        private const val WAVE_WIDTH_WEIGHT = 0.4f
        private const val WAVE_SPACER_WEIGHT = 0.6f
        private const val TIMER_INTERVAL_MS = 500L
        /** Tools row is dimmed until Clipboard / Small mode are built. */
        private const val TOOLS_DIM_ALPHA = 0.4f
        private const val TOOLS_TEXT_SP = 15f
        private const val TOOL_ICON_DP = 20
        private const val TOOL_LABEL_GAP_DP = 6
    }
}
