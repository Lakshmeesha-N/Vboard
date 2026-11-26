package app.vboard

import android.content.Context
import android.graphics.Canvas
import android.graphics.ColorFilter
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.drawable.Drawable
import kotlin.math.roundToInt

/** Plain white back arrow, no fill. Tools toggle open state. */
class BackArrowDrawable(context: Context) : Drawable() {

    private val density = context.resources.displayMetrics.density
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFFFFFFFF.toInt()
        style = Paint.Style.STROKE
        strokeWidth = 2f * density
        strokeCap = Paint.Cap.ROUND
    }
    private val boxPx = 17f * density

    override fun draw(canvas: Canvas) {
        val b = bounds
        if (b.isEmpty) return
        val dx = b.exactCenterX() - 8.5f * density
        val dy = b.exactCenterY() - 8.5f * density
        val midY = dy + 8.5f * density
        // Shaft.
        canvas.drawLine(dx + 12.5f * density, midY, dx + 4.5f * density, midY, paint)
        // Head.
        canvas.drawLine(dx + 4.5f * density, midY, dx + 7.5f * density, dy + 5.5f * density, paint)
        canvas.drawLine(dx + 4.5f * density, midY, dx + 7.5f * density, dy + 11.5f * density, paint)
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
