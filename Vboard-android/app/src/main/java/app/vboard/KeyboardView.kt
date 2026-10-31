package app.vboard

import android.content.Context
import android.util.TypedValue
import android.view.Gravity
import android.widget.LinearLayout
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

class KeyboardView(context: Context) : LinearLayout(context) {

    interface Listener {
        fun onText(text: String)
        fun onBackspace()
        fun onEnter()
        fun onShiftChanged(capsLock: Boolean)
        fun onGlobe()
        fun onSymbolsStub()
    }

    var listener: Listener? = null

    private enum class ShiftState { OFF, SHIFTED, CAPS }

    private var shiftState = ShiftState.OFF
    private var lastShiftTapMs: Long = 0
    private var shiftKey: KeyButton? = null

    init {
        orientation = VERTICAL
        setBackgroundColor(0xFF17181B.toInt())
        val side = dp(6)
        setPadding(side, dp(6), side, 0)
        buildRows()
        ViewCompat.setOnApplyWindowInsetsListener(this) { v, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(side, dp(6), side, bars.bottom)
            insets
        }
    }

    fun resetShift() {
        shiftState = ShiftState.OFF
        refreshShiftKey()
    }

    private fun buildRows() {
        addRow(KeyLayouts.NumberRow.map { label -> KeySpec(label, 1f, false) { onLetter(label) } })
        addRow(KeyLayouts.RowTop.map { label -> KeySpec(label, 1f, false) { onLetter(label) } })
        addRow(KeyLayouts.RowMiddle.map { label -> KeySpec(label, 1f, false) { onLetter(label) } })

        val bottomRow = mutableListOf<KeySpec>()
        bottomRow += KeySpec(KeyLayouts.SHIFT_LABEL, 1.5f, true) { onShiftTap() }
        KeyLayouts.RowBottom.forEach { label ->
            bottomRow += KeySpec(label, 1f, false) { onLetter(label) }
        }
        bottomRow += KeySpec(KeyLayouts.BACKSPACE_LABEL, 1.5f, true) { listener?.onBackspace() }
        addRow(bottomRow)
        shiftKey = (getChildAt(3) as LinearLayout).getChildAt(0) as KeyButton

        addRow(
            listOf(
                KeySpec(KeyLayouts.KEY_SYMBOLS, 1.2f, true) { listener?.onSymbolsStub() },
                KeySpec(KeyLayouts.GLOBE_LABEL, 0.9f, true) { listener?.onGlobe() },
                KeySpec(KeyLayouts.KEY_COMMA, 0.9f, false) { onLetter(",") },
                KeySpec(KeyLayouts.SPACE_LABEL, 4.2f, true, smallText = true) { onLetter(" ") },
                KeySpec(KeyLayouts.KEY_PERIOD, 0.9f, false) { onLetter(".") },
                KeySpec(KeyLayouts.ENTER_LABEL, 1.6f, true, enterKey = true) { listener?.onEnter() },
            )
        )
    }

    private fun onLetter(base: String) {
        val out = if (base.length == 1 && base[0].isLetter()) {
            if (shiftState == ShiftState.OFF) base.lowercase() else base.uppercase()
        } else {
            base
        }
        listener?.onText(out)
        if (shiftState == ShiftState.SHIFTED) {
            shiftState = ShiftState.OFF
            refreshShiftKey()
        }
    }

    private fun onShiftTap() {
        val now = System.currentTimeMillis()
        shiftState = when {
            shiftState == ShiftState.OFF && now - lastShiftTapMs < DOUBLE_TAP_MS -> ShiftState.CAPS
            shiftState == ShiftState.OFF -> ShiftState.SHIFTED
            shiftState == ShiftState.SHIFTED && now - lastShiftTapMs < DOUBLE_TAP_MS -> ShiftState.CAPS
            shiftState == ShiftState.SHIFTED -> ShiftState.OFF
            else -> ShiftState.OFF
        }
        lastShiftTapMs = now
        refreshShiftKey()
        listener?.onShiftChanged(shiftState == ShiftState.CAPS)
    }

    private fun refreshShiftKey() {
        val key = shiftKey ?: return
        key.text = if (shiftState == ShiftState.CAPS) KeyLayouts.CAPS_LABEL else KeyLayouts.SHIFT_LABEL
        key.isSelected = shiftState != ShiftState.OFF
        key.alpha = if (shiftState == ShiftState.OFF) 1f else 0.55f
    }

    private data class KeySpec(
        val label: String,
        val weight: Float,
        val modifier: Boolean,
        val smallText: Boolean = false,
        val enterKey: Boolean = false,
        val action: () -> Unit,
    )

    private fun addRow(keys: List<KeySpec>) {
        val row = LinearLayout(context).apply {
            orientation = HORIZONTAL
            gravity = Gravity.CENTER
            layoutParams = LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT)
        }
        keys.forEach { spec ->
            val key = KeyButton(context).apply {
                text = spec.label
                setModifier(spec.modifier)
                gravity = Gravity.CENTER
                setTextSize(
                    TypedValue.COMPLEX_UNIT_SP,
                    if (spec.smallText) 12f else 19f
                )
                if (spec.enterKey) setTextColor(0xFF7DD3FC.toInt()) else setTextColor(0xFFFFFFFF.toInt())
                onKeyDown = spec.action
                val margin = dp(3)
                layoutParams = LayoutParams(0, dp(KEY_HEIGHT_DP), spec.weight).apply {
                    setMargins(margin, margin, margin, margin)
                }
            }
            row.addView(key)
        }
        addView(row)
    }

    private fun dp(value: Int): Int =
        (value * resources.displayMetrics.density).toInt()

    companion object {
        private const val KEY_HEIGHT_DP = 58
        private const val DOUBLE_TAP_MS = 400L
    }
}
