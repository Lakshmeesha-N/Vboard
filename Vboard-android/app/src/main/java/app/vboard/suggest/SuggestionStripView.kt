package app.vboard.suggest

import android.content.Context
import android.util.TypedValue
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView

/**
 * Three-slot English word suggestion strip for the idle top bar.
 * GONE whenever it holds no words; taps report the picked word.
 * Android view code only — ranking lives in [Suggester].
 */
class SuggestionStripView(context: Context) : LinearLayout(context) {

    /** Called with the tapped word on ACTION_DOWN. */
    var onPick: ((String) -> Unit)? = null

    private val slots = ArrayList<TextView>(MAX_SLOTS)
    private val dividers = ArrayList<View>(MAX_SLOTS - 1)

    init {
        orientation = HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        visibility = GONE
        isFocusable = false
        repeat(MAX_SLOTS) { index ->
            TextView(context).apply {
                gravity = Gravity.CENTER
                setTextColor(0xFFFFFFFF.toInt())
                setTextSize(TypedValue.COMPLEX_UNIT_SP, SUGGESTION_TEXT_SP)
                maxLines = 1
                isSingleLine = true
                ellipsize = android.text.TextUtils.TruncateAt.END
                isFocusable = false
                isClickable = true
                layoutParams = LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f)
                arm(this)
                addView(this)
                slots += this
            }
            if (index < MAX_SLOTS - 1) {
                View(context).apply {
                    setBackgroundColor(DIVIDER_COLOR.toInt())
                    visibility = GONE
                    isFocusable = false
                    layoutParams = LayoutParams(dp(DIVIDER_WIDTH_DP), dp(DIVIDER_HEIGHT_DP))
                    addView(this)
                    dividers += this
                }
            }
        }
    }

    /** Shows up to [MAX_SLOTS] words; empty hides the whole strip. */
    fun setSuggestions(words: List<String>) {
        val shown = words.take(MAX_SLOTS)
        for (i in slots.indices) {
            val slot = slots[i]
            if (i < shown.size) {
                slot.text = shown[i]
                slot.visibility = VISIBLE
            } else {
                slot.text = ""
                slot.visibility = GONE
            }
        }
        // A divider shows only between two visible slots; all hide with the strip.
        for (i in dividers.indices) {
            dividers[i].visibility = if (i + 1 < shown.size) VISIBLE else GONE
        }
        visibility = if (shown.isEmpty()) GONE else VISIBLE
    }

    fun clear() {
        for (slot in slots) {
            slot.text = ""
            slot.visibility = GONE
        }
        for (divider in dividers) divider.visibility = GONE
        visibility = GONE
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private fun arm(slot: TextView) {
        slot.setOnTouchListener { touched, event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    if (!touched.isEnabled) return@setOnTouchListener false
                    touched.isPressed = true
                    touched.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                    (touched as TextView).text.toString().takeIf { it.isNotEmpty() }?.let { onPick?.invoke(it) }
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

    companion object {
        const val MAX_SLOTS = 3

        /** Suggestion label size; the idle-row spacer is two "M"s at this size. */
        const val SUGGESTION_TEXT_SP = 16f

        /** Mid-grey dividers that stand out on the dark bar, 2dp thick. */
        private const val DIVIDER_COLOR = 0xFF5A5E66
        private const val DIVIDER_WIDTH_DP = 2
        private const val DIVIDER_HEIGHT_DP = 14
    }
}
