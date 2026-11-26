package app.vboard

import android.content.Context
import android.graphics.Canvas
import android.graphics.ColorFilter
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.RectF
import android.graphics.drawable.Drawable
import kotlin.math.roundToInt

/** Mini keyboard glyph for the return-to-full-keyboard button. */
class KeyboardIconDrawable(context: Context) : Drawable() {

    private val density = context.resources.displayMetrics.density
    private val stroke = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFFFFFFFF.toInt()
        style = Paint.Style.STROKE
        strokeWidth = 1.5f * density
        strokeCap = Paint.Cap.ROUND
    }
    private val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFFFFFFFF.toInt() }
    private val boxPx = 24f * density
    private val rect = RectF()

    override fun draw(canvas: Canvas) {
        val b = bounds
        if (b.isEmpty) return
        val dx = b.exactCenterX() - 12f * density
        val dy = b.exactCenterY() - 12f * density
        // Frame.
        rect.set(dx + 3f * density, dy + 6f * density, dx + 21f * density, dy + 18f * density)
        canvas.drawRoundRect(rect, 2.5f * density, 2.5f * density, stroke)
        // Keys.
        for (i in 0..2) {
            val left = dx + (6f + 5f * i) * density
            rect.set(left, dy + 8.5f * density, left + 2f * density, dy + 10.5f * density)
            canvas.drawRect(rect, fill)
        }
        // Spacebar.
        rect.set(dx + 9f * density, dy + 13f * density, dx + 15f * density, dy + 14.5f * density)
        canvas.drawRect(rect, fill)
    }

    override fun getIntrinsicWidth(): Int = boxPx.roundToInt()

    override fun getIntrinsicHeight(): Int = boxPx.roundToInt()

    override fun setAlpha(alpha: Int) {
        stroke.alpha = alpha
        fill.alpha = alpha
    }

    override fun setColorFilter(colorFilter: ColorFilter?) {
        stroke.colorFilter = colorFilter
        fill.colorFilter = colorFilter
    }

    override fun getOpacity(): Int = PixelFormat.TRANSLUCENT
}
