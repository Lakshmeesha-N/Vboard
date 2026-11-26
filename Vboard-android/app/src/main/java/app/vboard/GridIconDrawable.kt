package app.vboard

import android.content.Context
import android.graphics.Canvas
import android.graphics.ColorFilter
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.RectF
import android.graphics.drawable.Drawable
import kotlin.math.roundToInt

/** Plain 2x2 grid of rounded squares; no glow. Tools toggle icon. */
class GridIconDrawable(context: Context) : Drawable() {

    private val density = context.resources.displayMetrics.density
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFFFFFFFF.toInt() }
    private val boxPx = 17f * density
    private val cell = 6.5f * density
    private val gap = 2f * density
    private val radius = 2f * density
    private val rect = RectF()

    override fun draw(canvas: Canvas) {
        val b = bounds
        if (b.isEmpty) return
        val total = cell * 2 + gap
        var y = b.exactCenterY() - total / 2
        repeat(2) {
            var x = b.exactCenterX() - total / 2
            repeat(2) {
                rect.set(x, y, x + cell, y + cell)
                canvas.drawRoundRect(rect, radius, radius, paint)
                x += cell + gap
            }
            y += cell + gap
        }
    }

    override fun getIntrinsicWidth(): Int = boxPx.roundToInt()

    override fun getIntrinsicHeight(): Int = boxPx.roundToInt()

    override fun setAlpha(alpha: Int) {
        paint.alpha = alpha
    }

    override fun setColorFilter(colorFilter: ColorFilter?) {
        paint.colorFilter = colorFilter
    }

    override fun getOpacity(): Int = PixelFormat.TRANSLUCENT
}
