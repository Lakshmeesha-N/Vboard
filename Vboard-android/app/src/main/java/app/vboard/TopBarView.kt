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
    }

    var listener: Listener? = null

    private val idleRow: LinearLayout
    private val pill: LinearLayout
    private val wave: WaveformView
    private val timerText: TextView
    private var undoButton: TextView? = null
    private var cancelButton: TextView? = null
    private var confirmButton: TextView? = null
    private var recordStartMs = 0L

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
        idleRow.addView(
            makeButton("Voice input", R.drawable.topbar_button_background, VoiceBarsDrawable(context)) {
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
            makeButton("AI actions", R.drawable.ai_ring_background, null) {
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
    }

    fun showIdle() {
        idleRow.visibility = VISIBLE
        pill.visibility = GONE
        stopTimer()
        setPillEnabled(true)
        wave.reset()
    }

    fun showRecording() {
        idleRow.visibility = GONE
        pill.visibility = VISIBLE
        setPillEnabled(true)
        wave.reset()
        startTimer()
    }

    fun showProcessing() {
        idleRow.visibility = GONE
        pill.visibility = VISIBLE
        stopTimer()
        setPillEnabled(false)
    }

    /** Undo is visible only in the idle bar, after an AI edit. */
    fun setUndoVisible(visible: Boolean) {
        undoButton?.visibility = if (visible) VISIBLE else GONE
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
        onDown: () -> Unit,
    ): AppCompatImageButton {
        return AppCompatImageButton(context).apply {
            contentDescription = description
            background = ContextCompat.getDrawable(context, backgroundRes)
            if (icon != null) setImageDrawable(icon)
            scaleType = ImageView.ScaleType.CENTER
            isFocusable = false
            isClickable = true
            val size = dp(BUTTON_DP)
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
        private const val GAP_DP = 8
        private const val WAVE_HEIGHT_DP = 40

        /** Wave takes ~40% of the pill's free width, right-aligned by the spacer. */
        private const val WAVE_WIDTH_WEIGHT = 0.4f
        private const val WAVE_SPACER_WEIGHT = 0.6f
        private const val TIMER_INTERVAL_MS = 500L
    }
}
