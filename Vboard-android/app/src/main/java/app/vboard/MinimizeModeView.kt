package app.vboard

import android.content.Context
import android.content.res.ColorStateList
import android.util.AttributeSet
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import androidx.appcompat.widget.AppCompatImageButton
import androidx.core.content.ContextCompat

/**
 * Small mode: a floating pill with three states.
 * Idle: [mic] [keyboard] [backspace], vertical or horizontal. The keyboard
 * button flips vertical to horizontal, and from horizontal back to the full
 * keyboard. Recording is always a compact horizontal bar (dotted wave, gray
 * X, white check). Processing shows a spinner.
 */
class MinimizeModeView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0,
) : LinearLayout(context, attrs, defStyleAttr) {

    interface Listener {
        fun onMicClick()
        fun onCheckClick()
        fun onCancelClick()
        fun onDeleteClick()
        fun onKeyboardClick()
        fun onPillDragged(dxPx: Int, dyPx: Int)
        fun onPillDragEnd()
    }

    var listener: Listener? = null

    private var pillOrientation = MinimizePolicy.Orientation.VERTICAL
    private var showing = MinimizePolicy.PillState.IDLE

    private val idleRowV: LinearLayout
    private val idleRowH: LinearLayout
    private val recRow: LinearLayout
    private val wave: WaveformView
    private val spinner: ProgressBar

    private var recordingUi = false

    private val touchSlop = android.view.ViewConfiguration.get(context).scaledTouchSlop
    private var downX = 0f
    private var downY = 0f
    private var lastX = 0f
    private var lastY = 0f
    private var dragging = false

    init {
        setOrientation(LinearLayout.VERTICAL)
        gravity = Gravity.CENTER_HORIZONTAL
        // Clickable root so drags starting on pill gaps keep the gesture.
        isClickable = true
        isFocusable = false
        background = ContextCompat.getDrawable(context, R.drawable.recording_pill_background)
        val pad = dp(6)
        setPadding(pad, dp(4), pad, dp(4))
        layoutParams = LayoutParams(LayoutParams.WRAP_CONTENT, LayoutParams.WRAP_CONTENT)

        idleRowV = LinearLayout(context).apply {
            orientation = VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            isFocusable = false
        }
        idleRowV.addView(micButton())
        idleRowV.addView(keyboardButton())
        idleRowV.addView(deleteButton())
        addView(idleRowV)

        idleRowH = LinearLayout(context).apply {
            orientation = HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            isFocusable = false
            visibility = GONE
        }
        idleRowH.addView(micButton())
        idleRowH.addView(keyboardButton())
        idleRowH.addView(deleteButton())
        addView(idleRowH)

        wave = WaveformView(context).apply {
            layoutParams = LayoutParams(dp(REC_WAVE_WIDTH_DP), dp(WAVE_HEIGHT_DP))
        }
        recRow = LinearLayout(context).apply {
            orientation = HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            isFocusable = false
            visibility = GONE
            addView(wave)
            addView(cancelButton())
            addView(checkButton())
        }
        addView(recRow)

        spinner = ProgressBar(context).apply {
            isIndeterminate = true
            indeterminateTintList = ColorStateList.valueOf(0xFFFFFFFF.toInt())
            visibility = GONE
            layoutParams = LayoutParams(dp(SPINNER_DP), dp(SPINNER_DP)).apply {
                gravity = Gravity.CENTER_HORIZONTAL
            }
        }
        addView(spinner)

        render()
    }

    fun setOrientation(value: MinimizePolicy.Orientation) {
        pillOrientation = value
        render()
    }

    fun showIdle() {
        showing = MinimizePolicy.PillState.IDLE
        recordingUi = false
        render()
    }

    fun showRecording() {
        showing = MinimizePolicy.PillState.RECORDING
        recordingUi = true
        wave.reset()
        render()
    }

    fun showProcessing() {
        showing = MinimizePolicy.PillState.PROCESSING
        recordingUi = false
        render()
    }

    /** Feeds live amplitude to the wave view while recording. */
    fun setAmplitude(raw: Float) {
        if (!recordingUi) return
        wave.setRawAmplitude(raw)
    }

    private fun render() {
        idleRowV.visibility = GONE
        idleRowH.visibility = GONE
        recRow.visibility = GONE
        spinner.visibility = GONE
        val vertical = pillOrientation == MinimizePolicy.Orientation.VERTICAL
        when (showing) {
            MinimizePolicy.PillState.IDLE -> if (vertical) idleRowV.show() else idleRowH.show()
            MinimizePolicy.PillState.RECORDING -> recRow.show()
            MinimizePolicy.PillState.PROCESSING -> spinner.show()
        }
    }

    private fun micButton() = AppCompatImageButton(context).apply {
        contentDescription = "Voice input"
        background = ContextCompat.getDrawable(context, R.drawable.topbar_button_background)
        setImageDrawable(VoiceBarsDrawable(context))
        scaleType = ImageView.ScaleType.CENTER
        isFocusable = false
        isClickable = true
        val size = dp(MIC_BUTTON_DP)
        layoutParams = LayoutParams(size, size)
        arm(this) { listener?.onMicClick() }
    }

    private fun keyboardButton() = AppCompatImageButton(context).apply {
        contentDescription = "Back to full keyboard"
        background = ContextCompat.getDrawable(context, R.drawable.topbar_button_background)
        setImageDrawable(KeyboardIconDrawable(context))
        scaleType = ImageView.ScaleType.CENTER
        isFocusable = false
        isClickable = true
        val size = dp(MIC_BUTTON_DP)
        layoutParams = LayoutParams(size, size)
        arm(this) { listener?.onKeyboardClick() }
    }

    private fun checkButton() = TextView(context).apply {
        contentDescription = "Stop and send recording"
        text = "✓"
        setTextColor(0xFF1E2025.toInt())
        textSize = 20f
        gravity = Gravity.CENTER
        isFocusable = false
        isClickable = true
        background = ContextCompat.getDrawable(context, R.drawable.confirm_button_background)
        val size = dp(MIC_BUTTON_DP)
        layoutParams = LayoutParams(size, size).apply { marginStart = dp(GAP_DP) }
        arm(this) { listener?.onCheckClick() }
    }

    private fun cancelButton() = TextView(context).apply {
        contentDescription = "Cancel recording"
        text = "✕"
        setTextColor(0xFF9AA0A6.toInt())
        textSize = 20f
        gravity = Gravity.CENTER
        isFocusable = false
        isClickable = true
        val size = dp(BUTTON_DP)
        layoutParams = LayoutParams(size, size).apply { marginStart = dp(GAP_DP) }
        arm(this) { listener?.onCancelClick() }
    }

    /** Flush in the idle rows so all three buttons align in one line. */
    private fun deleteButton() = AppCompatImageButton(context).apply {
        contentDescription = "Delete"
        background = ContextCompat.getDrawable(context, R.drawable.topbar_button_background)
        setImageDrawable(BackspaceIconDrawable(context))
        scaleType = ImageView.ScaleType.CENTER
        isFocusable = false
        isClickable = true
        // Same 42dp as mic/keyboard so the vertical stack aligns in one line.
        val size = dp(MIC_BUTTON_DP)
        layoutParams = LayoutParams(size, size)
        arm(this, repeat = true) { listener?.onDeleteClick() }
    }

    /**
     * Drag the pill by its body; taps still fall through to the buttons.
     * Intercepts only after the touch slop is exceeded mid-move. Screen
     * coordinates keep the pill from fighting its own movement.
     */
    override fun onInterceptTouchEvent(ev: MotionEvent): Boolean {
        when (ev.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                downX = ev.rawX
                downY = ev.rawY
                lastX = ev.rawX
                lastY = ev.rawY
                dragging = false
            }
            MotionEvent.ACTION_MOVE -> {
                if (!dragging &&
                    (kotlin.math.abs(ev.rawX - downX) > touchSlop ||
                        kotlin.math.abs(ev.rawY - downY) > touchSlop)
                ) {
                    dragging = true
                    parent?.requestDisallowInterceptTouchEvent(true)
                    return true
                }
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> dragging = false
        }
        return dragging
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {
            MotionEvent.ACTION_MOVE -> {
                if (!dragging) return false
                listener?.onPillDragged(
                    (event.rawX - lastX).toInt(),
                    (event.rawY - lastY).toInt(),
                )
                lastX = event.rawX
                lastY = event.rawY
                return true
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                if (!dragging) return false
                dragging = false
                listener?.onPillDragEnd()
                return true
            }
        }
        return super.onTouchEvent(event)
    }

    /**
     * Buttons arm on DOWN but fire only on a clean tap UP. A drag starting
     * on a button turns into a move (the child gets CANCEL, never fires),
     * so shifting the pill can no longer flip it into another mode.
     * Delete additionally repeats while held, like the keyboard key.
     */
    private fun arm(view: android.view.View, repeat: Boolean = false, onTap: () -> Unit) {
        view.setOnTouchListener { touched, event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    if (!touched.isEnabled) return@setOnTouchListener false
                    touched.isPressed = true
                    touched.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                    if (repeat) startRepeat(touched, onTap)
                    true
                }
                MotionEvent.ACTION_UP -> {
                    val held = repeatFired
                    stopRepeat()
                    val fire = touched.isPressed && (!repeat || !held)
                    touched.isPressed = false
                    if (fire) {
                        touched.performClick()
                        onTap()
                    }
                    true
                }
                MotionEvent.ACTION_CANCEL -> {
                    stopRepeat()
                    touched.isPressed = false
                    true
                }
                else -> false
            }
        }
    }

    private var repeatTarget: android.view.View? = null
    private var repeatAction: (() -> Unit)? = null
    private var repeatFired = false
    private val repeatTick = object : Runnable {
        override fun run() {
            val target = repeatTarget
            if (target == null || !target.isPressed) return
            repeatFired = true
            repeatAction?.invoke()
            target.postDelayed(this, REPEAT_INTERVAL_MS)
        }
    }

    private fun startRepeat(view: android.view.View, action: () -> Unit) {
        stopRepeat()
        repeatTarget = view
        repeatAction = action
        repeatFired = false
        view.postDelayed(repeatTick, REPEAT_DELAY_MS)
    }

    private fun stopRepeat() {
        repeatTarget?.removeCallbacks(repeatTick)
        repeatTarget = null
        repeatAction = null
    }

    private fun android.view.View.show() {
        visibility = VISIBLE
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    companion object {
        private const val MIC_BUTTON_DP = 42
        private const val BUTTON_DP = 40
        private const val SPINNER_DP = 32
        private const val REC_WAVE_WIDTH_DP = 96
        private const val WAVE_HEIGHT_DP = 40
        private const val GAP_DP = 8
        private const val REPEAT_DELAY_MS = 400L
        private const val REPEAT_INTERVAL_MS = 50L
    }
}
