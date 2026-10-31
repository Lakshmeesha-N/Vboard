package app.vboard

/**
 * Maps raw mic peaks to display levels. A noise floor keeps silence
 * flat, gain lifts normal speech into the visible 0.5–0.8 band, and
 * asymmetric easing rises fast but falls a bit slower.
 * Pure Kotlin, no Android imports.
 */
class LoudnessMapper(
    private val floor: Float = 0.02f,
    private val gain: Float = 6f,
    private val attack: Float = 0.7f,
    private val release: Float = 0.18f,
) {
    var value: Float = 0f
        private set

    /** Stateless floor+gain scale of one raw 0..1 peak. */
    fun map(raw: Float): Float = ((raw - floor) * gain).coerceIn(0f, 1f)

    /** Feeds one raw peak, returns the new eased display level. */
    fun update(raw: Float): Float {
        val target = map(raw)
        val rate = if (target > value) attack else release
        value += (target - value) * rate
        return value
    }

    fun reset() {
        value = 0f
    }
}
