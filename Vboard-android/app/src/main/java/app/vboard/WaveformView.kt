package app.vboard

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View
import kotlin.math.sin

/**
 * Live dotted waveform for the recording pill. Amplitude is scaled
 * through [LoudnessMapper] so speech reads clearly and silence sits flat.
 */
class WaveformView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0,
) : View(context, attrs, defStyleAttr) {

    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFF9AA0A6.toInt()
    }
    private val smoother = LoudnessMapper()
    private var phase = 0f

    /** Feeds a raw 0..1 mic level; safe to call from any thread. */
    fun setRawAmplitude(raw: Float) {
        smoother.update(raw)
        phase += 0.45f
        post { invalidate() }
    }

    fun reset() {
        smoother.reset()
        phase = 0f
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val dots = DOT_COUNT
        val w = width.toFloat()
        val h = height.toFloat()
        if (w <= 0 || h <= 0) return
        val step = w / (dots + 1)
        val level = smoother.value
        for (i in 0 until dots) {
            val wave = 0.35f + 0.65f * (0.5f + 0.5f * sin(phase + i * 0.7f).toFloat())
            val dotH = (MIN_FRAC + level * wave * (1f - MIN_FRAC)) * h * 0.9f
            val cx = step * (i + 1)
            val cy = h / 2f
            val r = (DOT_R_DP * resources.displayMetrics.density)
                .coerceAtMost(dotH / 2f + 1f)
            canvas.drawCircle(cx, cy - dotH / 2f + r, r, paint)
            canvas.drawCircle(cx, cy + dotH / 2f - r, r, paint)
            if (dotH > r * 4) {
                canvas.drawRect(cx - r, cy - dotH / 2f + r, cx + r, cy + dotH / 2f - r, paint)
            }
        }
    }

    companion object {
        private const val DOT_COUNT = 22
        private const val MIN_FRAC = 0.08f
        private const val DOT_R_DP = 1.6f
    }
}
