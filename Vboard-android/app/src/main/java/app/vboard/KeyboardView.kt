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
        fun onBackspaceRepeat(): Boolean
        fun onEnter()
        fun onShiftChanged(capsLock: Boolean)
        fun onGlobe()
        fun onSymbolsStub()
    }

    var listener: Listener? = null
    var topBarListener: TopBarView.Listener? = null
        set(value) {
            field = value
            topBar?.listener = value
        }

    private var topBar: TopBarView? = null

    private var capsOn = false
    private var shiftKey: KeyButton? = null
    private var backspaceKey: KeyButton? = null
    private val letterKeys = mutableListOf<KeyButton>()

    init {
        orientation = VERTICAL
        setBackgroundColor(0xFF17181B.toInt())
        val side = dp(6)
        setPadding(side, dp(6), side, 0)
        TopBarView(context).also {
            it.listener = topBarListener
            it.layoutParams = LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT)
            addView(it)
            topBar = it
        }
        buildRows()
        ViewCompat.setOnApplyWindowInsetsListener(this) { v, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(side, dp(6), side, bars.bottom)
            insets
        }
    }

    fun resetShift() {
        capsOn = false
        refreshShiftKey()
    }

    fun cancelKeyRepeats() {
        backspaceKey?.stopRepeat()
    }

    fun showIdleBar() {
        topBar?.showIdle()
    }

    fun showRecordingBar() {
        topBar?.showRecording()
    }

    fun showProcessingBar() {
        topBar?.showProcessing()
    }

    fun setRecordingAmplitude(raw: Float) {
        topBar?.setAmplitude(raw)
    }

    fun setUndoVisible(visible: Boolean) {
        topBar?.setUndoVisible(visible)
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        ViewCompat.requestApplyInsets(this)
    }

    fun refreshInsets() {
        ViewCompat.requestApplyInsets(this)
    }

    private fun buildRows() {
        addRow(KeyLayouts.NumberRow.map { label -> KeySpec(label, 1f, false) { onLetter(label) } })
        addRow(KeyLayouts.RowTop.map { label -> KeySpec(label, 1f, false, isLetter = true) { onLetter(label) } })
        addRow(KeyLayouts.RowMiddle.map { label -> KeySpec(label, 1f, false, isLetter = true) { onLetter(label) } })

        val bottomRow = mutableListOf<KeySpec>()
        bottomRow += KeySpec(KeyLayouts.SHIFT_LABEL, 1.5f, true) { onShiftTap() }
        KeyLayouts.RowBottom.forEach { label ->
            bottomRow += KeySpec(label, 1f, false, isLetter = true) { onLetter(label) }
        }
        bottomRow += KeySpec(
            KeyLayouts.BACKSPACE_LABEL, 1.5f, true,
            repeatOnHold = true,
            onRepeat = { listener?.onBackspaceRepeat() == true },
        ) { listener?.onBackspace() }
        val shiftRow = addRow(bottomRow)
        shiftKey = shiftRow.first()
        backspaceKey = shiftRow.last()
        refreshShiftKey()

        addRow(
            listOf(
                KeySpec(KeyLayouts.KEY_SYMBOLS, 1.2f, true) { listener?.onSymbolsStub() },
                KeySpec(KeyLayouts.KEY_COMMA, 0.9f, false) { onLetter(",") },
                KeySpec(
                    KeyLayouts.SPACE_LABEL, 5.1f, true, smallText = true,
                    fireOnDown = false,
                    onLongPress = { listener?.onGlobe() },
                ) { onLetter(" ") },
                KeySpec(KeyLayouts.KEY_PERIOD, 0.9f, false) { onLetter(".") },
                KeySpec(KeyLayouts.ENTER_LABEL, 1.6f, true, enterKey = true) { listener?.onEnter() },
            )
        )
    }

    private fun onLetter(base: String) {
        listener?.onText(KeyLayouts.applyCaps(base, capsOn))
    }

    private fun onShiftTap() {
        capsOn = !capsOn
        refreshShiftKey()
        listener?.onShiftChanged(capsOn)
    }

    private fun refreshShiftKey() {
        val key = shiftKey ?: return
        key.text = if (capsOn) KeyLayouts.CAPS_LABEL else KeyLayouts.SHIFT_LABEL
        key.isSelected = capsOn
        key.setCapsOn(capsOn)
        letterKeys.forEach { it.text = KeyLayouts.applyCaps(it.tag as String, capsOn) }
    }

    private data class KeySpec(
        val label: String,
        val weight: Float,
        val modifier: Boolean,
        val smallText: Boolean = false,
        val enterKey: Boolean = false,
        val isLetter: Boolean = false,
        val fireOnDown: Boolean = true,
        val repeatOnHold: Boolean = false,
        val onLongPress: (() -> Unit)? = null,
        val onRepeat: (() -> Boolean)? = null,
        val action: () -> Unit,
    )

    private fun addRow(keys: List<KeySpec>): List<KeyButton> {
        val row = LinearLayout(context).apply {
            orientation = HORIZONTAL
            gravity = Gravity.CENTER
            layoutParams = LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT)
        }
        val buttons = mutableListOf<KeyButton>()
        keys.forEach { spec ->
            val key = KeyButton(context).apply {
                text = spec.label
                setModifier(spec.modifier)
                gravity = Gravity.CENTER
                setTextSize(
                    TypedValue.COMPLEX_UNIT_SP,
                    when {
                        spec.smallText -> KEY_SPACE_LABEL_SP
                        spec.modifier -> KEY_MODIFIER_LABEL_SP
                        else -> KEY_LABEL_SP
                    }
                )
                if (spec.enterKey) setTextColor(0xFF7DD3FC.toInt()) else setTextColor(0xFFFFFFFF.toInt())
                onKeyDown = spec.action
                onLongPress = spec.onLongPress
                fireOnDown = spec.fireOnDown
                repeatOnHold = spec.repeatOnHold
                onRepeat = spec.onRepeat
                if (spec.isLetter) tag = spec.label
                val margin = dp(3)
                layoutParams = LayoutParams(0, dp(KEY_ROW_HEIGHT_DP), spec.weight).apply {
                    setMargins(margin, margin, margin, margin)
                }
            }
            if (spec.isLetter) letterKeys += key
            row.addView(key)
            buttons += key
        }
        addView(row)
        return buttons
    }

    private fun dp(value: Int): Int =
        (value * resources.displayMetrics.density).toInt()

    companion object {
        private const val KEY_ROW_HEIGHT_DP = 51
        // Letters + numbers, bumped for visibility (was 19sp). Modifiers stay
        // one step smaller so ?123 never clips its narrow key. Spacebar label
        // stays smallest. Heights/widths/spacing unchanged.
        private const val KEY_LABEL_SP = 23f
        private const val KEY_MODIFIER_LABEL_SP = 21f
        private const val KEY_SPACE_LABEL_SP = 14f
    }
}
