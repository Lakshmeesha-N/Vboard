package app.vboard

import android.content.Context
import android.graphics.Canvas
import android.graphics.ColorFilter
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.RectF
import android.graphics.drawable.Drawable
import kotlin.math.roundToInt

/** White clipboard with clip tab and two text lines. Dimmed tools-row chip icon. */
class ClipboardIconDrawable(context: Context) : Drawable() {

    private val density = context.resources.displayMetrics.density
    private val white = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFFFFFFFF.toInt() }
    private val dark = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFF25272C.toInt() }
    private val boxPx = 24f * density
    private val rect = RectF()

    override fun draw(canvas: Canvas) {
        val b = bounds
        if (b.isEmpty) return
        val dx = b.exactCenterX() - 12f * density
        val dy = b.exactCenterY() - 12f * density
        // Board.
        rect.set(dx + 6.5f * density, dy + 5f * density, dx + 17.5f * density, dy + 20.5f * density)
        canvas.drawRoundRect(rect, 2f * density, 2f * density, white)
        // Text lines (dark on white).
        rect.set(dx + 9f * density, dy + 10f * density, dx + 15f * density, dy + 11f * density)
        canvas.drawRect(rect, dark)
        rect.set(dx + 9f * density, dy + 13f * density, dx + 15f * density, dy + 14f * density)
        canvas.drawRect(rect, dark)
        // Clip tab on top.
        rect.set(dx + 9.5f * density, dy + 2.5f * density, dx + 14.5f * density, dy + 6.5f * density)
        canvas.drawRoundRect(rect, 1.5f * density, 1.5f * density, white)
    }

    override fun getIntrinsicWidth(): Int = boxPx.roundToInt()

    override fun getIntrinsicHeight(): Int = boxPx.roundToInt()

    override fun setAlpha(alpha: Int) {
        white.alpha = alpha
    }

    override fun setColorFilter(colorFilter: ColorFilter?) {
        white.colorFilter = colorFilter
    }

    override fun getOpacity(): Int = PixelFormat.TRANSLUCENT
}
