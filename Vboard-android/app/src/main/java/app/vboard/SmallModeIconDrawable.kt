package app.vboard

import android.content.Context
import android.graphics.Canvas
import android.graphics.ColorFilter
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.RectF
import android.graphics.drawable.Drawable
import kotlin.math.roundToInt

/** Mini keyboard outline with a resize arrow. Dimmed tools-row chip icon. */
class SmallModeIconDrawable(context: Context) : Drawable() {

    private val density = context.resources.displayMetrics.density
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFFFFFFFF.toInt()
        style = Paint.Style.STROKE
        strokeWidth = 1.5f * density
        strokeCap = Paint.Cap.ROUND
    }
    private val boxPx = 24f * density
    private val rect = RectF()

    override fun draw(canvas: Canvas) {
        val b = bounds
        if (b.isEmpty) return
        val dx = b.exactCenterX() - 12f * density
        val dy = b.exactCenterY() - 12f * density
        // Keyboard frame.
        rect.set(dx + 3f * density, dy + 8f * density, dx + 21f * density, dy + 18f * density)
        canvas.drawRoundRect(rect, 2.5f * density, 2.5f * density, paint)
        // Sideways resize arrow.
        val midY = dy + 13f * density
        canvas.drawLine(dx + 7.5f * density, midY, dx + 16.5f * density, midY, paint)
        canvas.drawLine(dx + 7.5f * density, midY, dx + 10f * density, dy + 11f * density, paint)
        canvas.drawLine(dx + 7.5f * density, midY, dx + 10f * density, dy + 15f * density, paint)
        canvas.drawLine(dx + 16.5f * density, midY, dx + 14f * density, dy + 11f * density, paint)
        canvas.drawLine(dx + 16.5f * density, midY, dx + 14f * density, dy + 15f * density, paint)
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
