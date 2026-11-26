package app.vboard

import android.content.Context
import android.graphics.Paint
import android.graphics.Rect
import android.os.SystemClock
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.FrameLayout
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
        fun onSymbolsToggle()
    }

    var listener: Listener? = null
    var topBarListener: TopBarView.Listener? = null
        set(value) {
            field = value
            topBar?.listener = value
        }

    private var topBar: TopBarView? = null

    var minimizeListener: MinimizeModeView.Listener? = null
        set(value) {
            field = value
            minimizeBar?.listener = value
        }

    private var minimizeContainer: FrameLayout? = null
    private var minimizeBar: MinimizeModeView? = null
    private var minimized = false
    private var pillX = -1
    private var pillY = -1
    private val keyRows = mutableListOf<LinearLayout>()

    private var shiftState = KeyLayouts.ShiftState.OFF
    private var lastShiftTapMs = 0L
    private var symbolsOn = false
    private var symbolsTogglePending = false
    private val symbolsToggleRunnable = Runnable {
        symbolsTogglePending = false
        listener?.onSymbolsToggle()
    }
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
        MinimizeModeView(context).also {
            it.listener = minimizeListener
            minimizeBar = it
            minimizeContainer = FrameLayout(context).apply {
                visibility = GONE
                layoutParams = LayoutParams(LayoutParams.MATCH_PARENT, 0, 1f)
                addView(it)
            }
            addView(minimizeContainer)
        }
        buildRows()
        ViewCompat.setOnApplyWindowInsetsListener(this) { v, insets ->
            // Small mode owns its padding (transparent full layer); touching
            // it here would lift the pill and misplace its touches.
            if (!minimized) {
                val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
                v.setPadding(side, dp(6), side, bars.bottom)
            }
            insets
        }
    }

    fun resetShift() {
        shiftState = KeyLayouts.ShiftState.OFF
        lastShiftTapMs = 0L
        refreshShift()
    }

    fun toggleSymbols() {
        symbolsOn = !symbolsOn
        if (symbolsOn) shiftState = KeyLayouts.ShiftState.OFF
        rebuildKeys()
    }

    fun showLetters() {
        if (!symbolsOn) return
        symbolsOn = false
        shiftState = KeyLayouts.ShiftState.OFF
        rebuildKeys()
    }

    private fun rebuildKeys() {
        removeCallbacks(symbolsToggleRunnable)
        symbolsTogglePending = false
        cancelKeyRepeats()
        for (row in keyRows) removeView(row)
        keyRows.clear()
        letterKeys.clear()
        shiftKey = null
        backspaceKey = null
        buildRows()
        syncMinimizedVisibility()
    }

    fun cancelKeyRepeats() {
        backspaceKey?.stopRepeat()
    }

    fun showIdleBar() {
        if (minimized) {
            minimizeBar?.showIdle()
            applyMinimizePosition()
        } else {
            topBar?.showIdle()
        }
    }

    fun showRecordingBar() {
        if (minimized) {
            val bar = minimizeBar
            val lp = bar?.layoutParams as? FrameLayout.LayoutParams
            val anchorRight = if (bar != null && lp != null && bar.width > 0) {
                lp.leftMargin + bar.width
            } else {
                -1
            }
            bar?.showRecording()
            if (anchorRight >= 0) minimizeContainer?.post { anchorRecordingLeft(anchorRight) }
        } else {
            topBar?.showRecording()
        }
    }

    fun showProcessingBar() {
        if (minimized) {
            minimizeBar?.showProcessing()
            applyMinimizePosition()
        } else {
            topBar?.showProcessing()
        }
    }

    fun showAgentWorkingBar() {
        if (minimized) minimizeBar?.showIdle() else topBar?.showAgentWorking()
    }

    fun setRecordingAmplitude(raw: Float) {
        if (minimized) minimizeBar?.setAmplitude(raw) else topBar?.setAmplitude(raw)
    }

    fun setUndoVisible(visible: Boolean) {
        if (!minimized) topBar?.setUndoVisible(visible)
    }

    /** Hides keys and top bar; only the pill shows, pinned to the right edge. */
    fun showMinimized() {
        minimized = true
        syncMinimizedVisibility()
    }

    /** Restores keys and top bar; the pill hides. */
    fun showFullKeyboard() {
        minimized = false
        syncMinimizedVisibility()
        showIdleBar()
    }

    fun isMinimized(): Boolean = minimized

    fun setMinimizeOrientation(value: MinimizePolicy.Orientation) {
        minimizeBar?.setOrientation(value)
        // The wider face must not hang off-screen; pull it back inside.
        minimizeContainer?.post { clampMinimizePosition() }
    }

    private fun syncMinimizedVisibility() {
        if (minimized) {
            // Transparent full-height layer: no dark band, the app keeps its
            // size behind it, and only the pill is touchable via insets.
            setBackgroundColor(0x00000000.toInt())
            setPadding(0, 0, 0, 0)
            minimumHeight = resources.displayMetrics.heightPixels
        } else {
            val side = dp(6)
            setBackgroundColor(0xFF17181B.toInt())
            setPadding(side, dp(6), side, 0)
            minimumHeight = 0
        }
        topBar?.visibility = if (minimized) GONE else VISIBLE
        minimizeContainer?.visibility = if (minimized) VISIBLE else GONE
        for (row in keyRows) row.visibility = if (minimized) GONE else VISIBLE
        // Coming back to full keys must re-apply the navigation-bar bottom
        // padding at once; nothing else re-sends insets on this path.
        if (!minimized) refreshInsets()
    }

    /** Current pill top-left in px; (-1, -1) means never placed. */
    fun minimizePosition(): Pair<Int, Int> = pillX to pillY

    /** Restores a saved position once laid out; ignored when never placed. */
    fun setMinimizePosition(x: Int, y: Int) {
        pillX = x
        pillY = y
        minimizeContainer?.post { applyMinimizePosition() }
    }

    /** First open: right edge, vertically centered. */
    fun defaultMinimizePosition() {
        minimizeContainer?.post {
            val container = minimizeContainer ?: return@post
            val bar = minimizeBar ?: return@post
            pillX = (container.width - bar.width).coerceAtLeast(0)
            pillY = (container.height - bar.height).coerceAtLeast(0) / 2
            applyMinimizePosition()
        }
    }

    /** Nudges the pill by a drag delta, clamped inside the screen. */
    fun moveMinimizeBy(dx: Int, dy: Int) {
        if (pillX < 0 || pillY < 0) {
            val container = minimizeContainer
            val bar = minimizeBar
            if (container != null && bar != null && container.width > 0 && bar.width > 0) {
                pillX = (container.width - bar.width).coerceAtLeast(0)
                pillY = (container.height - bar.height).coerceAtLeast(0) / 2
            } else {
                defaultMinimizePosition()
                return
            }
        }
        pillX += dx
        pillY += dy
        clampMinimizePosition()
    }

    /** Pulls the pill back inside the screen; call after size changes. */
    private fun clampMinimizePosition() {
        if (pillX < 0 || pillY < 0) return
        val clamped = MinimizePolicy.clampPosition(
            pillX,
            pillY,
            (minimizeContainer?.width ?: 0) - (minimizeBar?.width ?: 0),
            (minimizeContainer?.height ?: 0) - (minimizeBar?.height ?: 0),
        )
        pillX = clamped.first
        pillY = clamped.second
        applyMinimizePosition()
    }

    /**
     * Recording bar grows leftward from the idle pill's right edge and stays
     * on screen; the idle position restores when it returns to idle.
     */
    private fun anchorRecordingLeft(anchorRight: Int) {
        val bar = minimizeBar ?: return
        val lp = bar.layoutParams as? FrameLayout.LayoutParams ?: return
        if (bar.width <= 0) return
        val maxLeft = ((minimizeContainer?.width ?: 0) - bar.width).coerceAtLeast(0)
        lp.leftMargin = MinimizePolicy.anchorRecordingLeft(anchorRight, bar.width, maxLeft)
        bar.layoutParams = lp
    }

    private fun applyMinimizePosition() {
        val bar = minimizeBar ?: return
        val lp = FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.WRAP_CONTENT,
            FrameLayout.LayoutParams.WRAP_CONTENT,
        )
        lp.leftMargin = pillX.coerceAtLeast(0)
        lp.topMargin = pillY.coerceAtLeast(0)
        bar.layoutParams = lp
    }

    /** Pill bounds in window coordinates for the touchable-region inset. */
    fun minimizeTouchableRect(): Rect? {
        if (!minimized) return null
        val bar = minimizeBar ?: return null
        if (bar.visibility != VISIBLE || bar.width <= 0 || bar.height <= 0) return null
        // Window coordinates, not screen: the inset region is window-relative
        // and a status-bar-sized offset kills the short horizontal pill.
        val loc = IntArray(2)
        bar.getLocationInWindow(loc)
        return Rect(loc[0], loc[1], loc[0] + bar.width, loc[1] + bar.height)
    }

    fun showSuggestions(words: List<String>) {
        topBar?.showSuggestions(words)
    }

    fun clearSuggestions() {
        topBar?.clearSuggestions()
    }

    fun setOnSuggestionPick(onPick: ((String) -> Unit)?) {
        topBar?.setOnSuggestionPick(onPick)
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
        val topLabels = if (symbolsOn) KeyLayouts.SymbolRowTop else KeyLayouts.RowTop
        val midLabels = if (symbolsOn) KeyLayouts.SymbolRowMiddle else KeyLayouts.RowMiddle
        val botLabels = if (symbolsOn) KeyLayouts.SymbolRowBottom else KeyLayouts.RowBottom
        val letterLayer = !symbolsOn
        addRow(topLabels.map { label -> KeySpec(label, 1f, false, isLetter = letterLayer) { onLetter(label) } })
        addRow(midLabels.map { label -> KeySpec(label, 1f, false, isLetter = letterLayer) { onLetter(label) } })

        val bottomRow = mutableListOf<KeySpec>()
        bottomRow += KeySpec(KeyLayouts.SHIFT_LABEL, 1.5f, true) { onShiftTap() }
        botLabels.forEach { label ->
            bottomRow += KeySpec(label, 1f, false, isLetter = letterLayer) { onLetter(label) }
        }
        bottomRow += KeySpec(
            KeyLayouts.BACKSPACE_LABEL, 1.5f, true,
            repeatOnHold = true,
            onRepeat = { listener?.onBackspaceRepeat() == true },
        ) { listener?.onBackspace() }
        val shiftRow = addRow(bottomRow)
        shiftKey = shiftRow.first()
        backspaceKey = shiftRow.last()
        refreshShift()

        addRow(
            listOf(
                KeySpec(
                    if (symbolsOn) KeyLayouts.KEY_ABC else KeyLayouts.KEY_SYMBOLS,
                    1.2f, true,
                ) { onSymbolsTap() },
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
        listener?.onText(KeyLayouts.applyCaps(base, KeyLayouts.shiftShowsUppercase(shiftState)))
        // One-shot shift is consumed by the next letter only; space and
        // punctuation leave it armed.
        if (shiftState == KeyLayouts.ShiftState.SINGLE && base.length == 1 && base[0].isLetter()) {
            shiftState = KeyLayouts.ShiftState.OFF
            refreshShift()
        }
    }

    private fun onShiftTap() {
        if (symbolsOn) return
        val now = SystemClock.uptimeMillis()
        val withinWindow = now - lastShiftTapMs <= KeyLayouts.DOUBLE_TAP_TIMEOUT_MS
        lastShiftTapMs = now
        shiftState = KeyLayouts.nextShiftState(shiftState, withinWindow)
        refreshShift()
    }

    /**
     * The toggle rebuild destroys the pressed key in the same frame, so its
     * highlight would never paint. Wait one short beat so the tap visibly
     * lights the key up, then swap layers. Double-taps while one is pending
     * are ignored (single-flight).
     */
    private fun onSymbolsTap() {
        if (symbolsTogglePending) return
        symbolsTogglePending = true
        postDelayed(symbolsToggleRunnable, SYMBOLS_TOGGLE_DELAY_MS)
    }

    override fun onDetachedFromWindow() {
        removeCallbacks(symbolsToggleRunnable)
        symbolsTogglePending = false
        super.onDetachedFromWindow()
    }

    /** Auto-caps (sentence start): arms one-shot shift when currently off. */
    fun setShiftSingle() {
        if (symbolsOn || shiftState != KeyLayouts.ShiftState.OFF) return
        lastShiftTapMs = 0L
        shiftState = KeyLayouts.ShiftState.SINGLE
        refreshShift()
    }

    /** Backspace cancels a pending one-shot shift; caps lock survives. */
    fun clearOneShotShift() {
        if (shiftState != KeyLayouts.ShiftState.SINGLE) return
        shiftState = KeyLayouts.ShiftState.OFF
        refreshShift()
    }

    private fun refreshShift() {
        val key = shiftKey ?: return
        val upper = KeyLayouts.shiftShowsUppercase(shiftState)
        // Monochrome states, same glyph, no new colors: off is the plain
        // outline arrow; armed/locked is bold (filled look); caps lock adds
        // a small underline bar. Letter case updates on the same frame.
        key.paint.isFakeBoldText = upper
        key.paintFlags = if (shiftState == KeyLayouts.ShiftState.CAPS) {
            key.paintFlags or Paint.UNDERLINE_TEXT_FLAG
        } else {
            key.paintFlags and Paint.UNDERLINE_TEXT_FLAG.inv()
        }
        key.text = KeyLayouts.SHIFT_LABEL
        key.setCapsOn(upper)
        key.isSelected = shiftState == KeyLayouts.ShiftState.CAPS
        // Capitals render at the original label size (23sp); lowercase keeps
        // the +2sp bump (25sp). The toggle already relabels every key on this
        // frame, so typing itself costs no extra layout pass.
        val letterSp = if (upper) KEY_LABEL_SP else KEY_LETTER_SP
        letterKeys.forEach {
            it.text = KeyLayouts.applyCaps(it.tag as String, upper)
            it.setTextSize(TypedValue.COMPLEX_UNIT_SP, letterSp)
        }
        listener?.onShiftChanged(shiftState == KeyLayouts.ShiftState.CAPS)
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

    private fun addRow(keys: List<KeySpec>, heightDp: Int = KEY_ROW_HEIGHT_DP): List<KeyButton> {
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
                        spec.isLetter -> KEY_LETTER_SP
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
                layoutParams = LayoutParams(0, dp(heightDp), spec.weight).apply {
                    setMargins(margin, margin, margin, margin)
                }
            }
            if (spec.isLetter) letterKeys += key
            row.addView(key)
            buttons += key
        }
        addView(row)
        keyRows += row
        return buttons
    }

    private fun dp(value: Int): Int =
        (value * resources.displayMetrics.density).toInt()

    companion object {
        private const val KEY_ROW_HEIGHT_DP = 51
        /** Beat between ?123/ABC tap highlight and the layer swap. */
        private const val SYMBOLS_TOGGLE_DELAY_MS = 120L
        // Letters-only bump for visibility (+2sp over the shared label size).
        // Numbers, symbols (?123 layer), comma/period use KEY_LABEL_SP;
        // modifiers (?123/ABC, Shift, Backspace, Enter) use
        // KEY_MODIFIER_LABEL_SP; spacebar stays smallest. Single a-z glyphs
        // still fit at 25sp in the unchanged 51dp keys with 3dp margins, so
        // heights/widths/spacing/layout are untouched. Pressed backgrounds
        // and the KeyButton touch path are untouched, so highlight colour
        // and typing speed are unchanged.
        private const val KEY_LABEL_SP = 23f
        private const val KEY_LETTER_SP = 25f
        private const val KEY_MODIFIER_LABEL_SP = 21f
        private const val KEY_SPACE_LABEL_SP = 14f
    }
}
