package app.vboard

import android.content.Context
import android.graphics.Canvas
import android.graphics.ColorFilter
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.RectF
import android.graphics.drawable.Drawable
import kotlin.math.roundToInt

class VoiceBarsDrawable(context: Context) : Drawable() {

    private val density = context.resources.displayMetrics.density
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFFFFFFFF.toInt() }
    private val boxPx = 24f * density
    private val barW = 2.5f * density
    private val gap = 2.5f * density
    private val heights = floatArrayOf(6f, 10f, 14f, 10f, 6f).map { it * density }.toFloatArray()
    private val rect = RectF()

    override fun draw(canvas: Canvas) {
        val b = bounds
        if (b.isEmpty) return
        val totalW = barW * 5 + gap * 4
        var x = b.exactCenterX() - totalW / 2
        val cy = b.exactCenterY()
        for (i in heights.indices) {
            val h = heights[i]
            rect.set(x, cy - h / 2, x + barW, cy + h / 2)
            canvas.drawRoundRect(rect, barW / 2, barW / 2, paint)
            x += barW + gap
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
