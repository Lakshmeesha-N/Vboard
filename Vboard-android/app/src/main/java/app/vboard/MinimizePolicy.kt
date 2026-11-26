package app.vboard

/**
 * Pure state rules for small mode; Android-free so JVM tests cover them.
 * The mic itself reuses the service voice flow unchanged (same guards, same
 * Recorder and stream-first send path), so no voice policy lives here.
 */
object MinimizePolicy {

    /** Pill layout direction; persisted, restored on open. */
    enum class Orientation { VERTICAL, HORIZONTAL }

    /** Which pill face shows; recording wins, then processing, else idle. */
    enum class PillState { IDLE, RECORDING, PROCESSING }

    /** Entering small mode is blocked mid-flight; the pill owns no send state. */
    fun canEnter(recording: Boolean, sending: Boolean): Boolean = !recording && !sending

    /** X cancels the recording only; it exists solely in the recording face. */
    fun isCancelEnabled(recording: Boolean): Boolean = recording

    /** Flip button toggles the pill direction. */
    fun flipped(current: Orientation): Orientation =
        if (current == Orientation.VERTICAL) Orientation.HORIZONTAL else Orientation.VERTICAL

    /** Derives the visible face from the send pipeline state. */
    fun pillState(recording: Boolean, sending: Boolean): PillState = when {
        recording -> PillState.RECORDING
        sending -> PillState.PROCESSING
        else -> PillState.IDLE
    }

    /** Keeps the dragged pill inside the screen; negative room clamps to zero. */
    fun clampPosition(x: Int, y: Int, maxX: Int, maxY: Int): Pair<Int, Int> =
        x.coerceIn(0, maxX.coerceAtLeast(0)) to y.coerceIn(0, maxY.coerceAtLeast(0))

    /**
     * Recording bar grows leftward: its left edge sits one bar-width left of
     * the idle pill's right edge, pinned inside the screen.
     */
    fun anchorRecordingLeft(anchorRight: Int, barWidth: Int, maxLeft: Int): Int =
        (anchorRight - barWidth).coerceIn(0, maxLeft.coerceAtLeast(0))
}
