package app.vboard

import android.content.Context
import android.graphics.drawable.Drawable
import android.util.AttributeSet
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
import android.widget.ImageView
import android.widget.LinearLayout
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
    }

    var listener: Listener? = null

    init {
        orientation = HORIZONTAL
        gravity = Gravity.END or Gravity.CENTER_VERTICAL
        setPadding(0, dp(2), dp(2), dp(2))
        addView(
            makeButton("Voice input", R.drawable.topbar_button_background, VoiceBarsDrawable(context)) {
                listener?.onVoiceClick()
            }
        )
        addView(
            makeButton("AI actions", R.drawable.ai_ring_background, null) {
                listener?.onAiClick()
            }
        )
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
            setOnTouchListener { v, event ->
                when (event.actionMasked) {
                    MotionEvent.ACTION_DOWN -> {
                        v.isPressed = true
                        v.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                        onDown()
                        true
                    }
                    MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                        v.isPressed = false
                        if (event.actionMasked == MotionEvent.ACTION_UP) v.performClick()
                        true
                    }
                    else -> false
                }
            }
        }
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    companion object {
        private const val BUTTON_DP = 40
        private const val GAP_DP = 8
    }
}
