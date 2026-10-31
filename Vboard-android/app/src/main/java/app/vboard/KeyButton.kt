package app.vboard

import android.content.Context
import android.util.AttributeSet
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
import androidx.appcompat.widget.AppCompatButton
import androidx.core.content.ContextCompat

class KeyButton @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = androidx.appcompat.R.attr.buttonStyle
) : AppCompatButton(context, attrs, defStyleAttr) {

    var onKeyDown: (() -> Unit)? = null

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

    override fun onTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                isPressed = true
                performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                onKeyDown?.invoke()
                return true
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                isPressed = false
                if (event.actionMasked == MotionEvent.ACTION_UP) performClick()
                return true
            }
        }
        return super.onTouchEvent(event)
    }
}
