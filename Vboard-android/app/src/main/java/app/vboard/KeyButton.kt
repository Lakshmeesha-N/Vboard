package app.vboard

import android.content.Context
import android.os.Handler
import android.os.Looper
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
    /** When true, holding the key repeats onRepeat after an initial delay. */
    var repeatOnHold: Boolean = false
    /** Return false to stop repeating (e.g. textbox is empty). */
    var onRepeat: (() -> Boolean)? = null

    // Main-thread handler and a single reused runnable: at most one repeat runs,
    // and the touch path allocates nothing.
    private val mainHandler = Handler(Looper.getMainLooper())
    private var repeatTick = 0
    private val repeatRunnable: Runnable = Runnable {
        if (!isPressed || !repeatOnHold) return@Runnable
        if (onRepeat?.invoke() == true) {
            repeatTick++
            mainHandler.postDelayed(repeatRunnable, KeyLayouts.RepeatTiming.delayForTick(repeatTick))
        }
    }

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

    /** Stops a running hold-to-repeat; safe to call when none is running. */
    fun stopRepeat() {
        mainHandler.removeCallbacks(repeatRunnable)
        repeatTick = 0
    }

    override fun onDetachedFromWindow() {
        removeCallbacks(longPressRunnable)
        stopRepeat()
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
                if (repeatOnHold) {
                    mainHandler.removeCallbacks(repeatRunnable)
                    repeatTick = 0
                    mainHandler.postDelayed(repeatRunnable, KeyLayouts.RepeatTiming.delayForTick(0))
                }
                return true
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                removeCallbacks(longPressRunnable)
                stopRepeat()
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
