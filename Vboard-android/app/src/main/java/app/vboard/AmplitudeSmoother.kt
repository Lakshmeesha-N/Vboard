package app.vboard

/**
 * Exponential moving average for mic amplitude so the wave pill
 * follows speech without jitter. Pure Kotlin, no Android imports.
 */
class AmplitudeSmoother(private val factor: Float = 0.35f) {
    var value: Float = 0f
        private set

    /** Feeds one raw 0..1 sample, returns the new smoothed value. */
    fun update(raw: Float): Float {
        val clamped = raw.coerceIn(0f, 1f)
        value += (clamped - value) * factor
        return value
    }

    fun reset() {
        value = 0f
    }
}
