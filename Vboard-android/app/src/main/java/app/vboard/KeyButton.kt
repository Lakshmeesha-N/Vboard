package app.vboard

import android.content.Context
import android.util.AttributeSet
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
import android.view.ViewConfiguration
import androidx.appcompat.widget.AppCompatButton
import androidx.core.content.ContextCompat

class KeyButton @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = androidx.appcompat.R.attr.buttonStyle
) : AppCompatButton(context, attrs, defStyleAttr) {

    var onKeyDown: (() -> Unit)? = null
    var onLongPress: (() -> Unit)? = null
    /** When false, onKeyDown fires on ACTION_UP so a long-press can replace the tap. */
    var fireOnDown: Boolean = true

    private var longPressFired = false
    private val longPressRunnable = Runnable {
        if (isPressed) {
            longPressFired = true
            performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
            onLongPress?.invoke()
        }
    }

    init {
        isFocusable = false
        isClickable = true
        setModifier(false)
        minHeight = 0
        minimumHeight = 0
    }

    fun setModifier(modifier: Boolean) {
        val bg = if (modifier) R.drawable.keycap_modifier_background else R.drawable.keycap_background
        background = ContextCompat.getDrawable(context, bg)
    }

    fun setCapsOn(active: Boolean) {
        val bg = if (active) R.drawable.keycap_shift_on_background else R.drawable.keycap_modifier_background
        background = ContextCompat.getDrawable(context, bg)
    }

    override fun onDetachedFromWindow() {
        removeCallbacks(longPressRunnable)
        isPressed = false
        longPressFired = false
        super.onDetachedFromWindow()
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                longPressFired = false
                isPressed = true
                performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                if (onLongPress != null) {
                    postDelayed(longPressRunnable, ViewConfiguration.getLongPressTimeout().toLong())
                }
                if (fireOnDown) onKeyDown?.invoke()
                return true
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                removeCallbacks(longPressRunnable)
                isPressed = false
                val fired = longPressFired
                longPressFired = false
                if (event.actionMasked == MotionEvent.ACTION_UP) {
                    performClick()
                    if (!fired && !fireOnDown) onKeyDown?.invoke()
                }
                return true
            }
        }
        return super.onTouchEvent(event)
    }
}
