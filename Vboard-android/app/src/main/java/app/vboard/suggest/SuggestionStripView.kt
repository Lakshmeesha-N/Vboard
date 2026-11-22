package app.vboard.suggest

import android.content.Context
import android.util.TypedValue
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
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

    init {
        orientation = HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        visibility = GONE
        isFocusable = false
        repeat(MAX_SLOTS) {
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
        visibility = if (shown.isEmpty()) GONE else VISIBLE
    }

    fun clear() {
        for (slot in slots) {
            slot.text = ""
            slot.visibility = GONE
        }
        visibility = GONE
    }

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

        /** Suggestion label size; the idle-row spacer is one "M" at this size. */
        const val SUGGESTION_TEXT_SP = 16f
    }
}
