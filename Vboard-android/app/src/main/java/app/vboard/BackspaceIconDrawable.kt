package app.vboard

import android.content.Context
import android.graphics.Canvas
import android.graphics.ColorFilter
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.RectF
import android.graphics.drawable.Drawable
import kotlin.math.roundToInt

/** Backspace key glyph (frame with an X) for the small-mode recording bar. */
class BackspaceIconDrawable(context: Context) : Drawable() {

    private val density = context.resources.displayMetrics.density
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFFFFFFFF.toInt()
        style = Paint.Style.STROKE
        strokeWidth = 1.5f * density
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }
    private val boxPx = 24f * density
    private val rect = RectF()

    override fun draw(canvas: Canvas) {
        val b = bounds
        if (b.isEmpty) return
        val dx = b.exactCenterX() - 12f * density
        val dy = b.exactCenterY() - 12f * density
        // Key frame.
        rect.set(dx + 3f * density, dy + 6f * density, dx + 21f * density, dy + 18f * density)
        canvas.drawRoundRect(rect, 2.5f * density, 2.5f * density, paint)
        // The X inside.
        canvas.drawLine(dx + 9.5f * density, dy + 9.5f * density, dx + 14.5f * density, dy + 14.5f * density, paint)
        canvas.drawLine(dx + 14.5f * density, dy + 9.5f * density, dx + 9.5f * density, dy + 14.5f * density, paint)
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
