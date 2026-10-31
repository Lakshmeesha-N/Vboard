package app.vboard

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.util.Arrays
import kotlin.math.abs

/**
 * Tap-to-record microphone capture. Records 16 kHz mono 16-bit PCM
 * into RAM only, then assembles an in-memory WAV via [WavBuilder].
 *
 * Never touches disk. Internal buffers are zeroed and dropped on
 * stop/cancel/release. Call [release] when the IME view goes away.
 */
class Recorder(
    private val onAmplitude: (Float) -> Unit,
    private val onAutoStop: () -> Unit,
) {
    sealed interface StartResult {
        data object Started : StartResult
        data object Failed : StartResult
    }

    @Volatile
    private var running = false
    private var thread: Thread? = null
    private var record: AudioRecord? = null
    private var pcm = ByteArray(0)
    private var frames = 0

    /** Starts capture. On [StartResult.Failed] nothing is left running. */
    @Synchronized
    fun start(): StartResult {
        shutDown()
        frames = 0
        val capacity = WavBuilder.maxFrames() * 2
        val minBuf = try {
            AudioRecord.getMinBufferSize(
                WavBuilder.SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
            )
        } catch (_: Exception) {
            return StartResult.Failed
        }
        if (minBuf <= 0) return StartResult.Failed
        val rec = try {
            AudioRecord(
                MediaRecorder.AudioSource.MIC,
                WavBuilder.SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                minBuf.coerceAtLeast(4096) * 2,
            )
        } catch (_: Exception) {
            return StartResult.Failed
        }
        if (rec.state != AudioRecord.STATE_INITIALIZED) {
            rec.release()
            return StartResult.Failed
        }
        try {
            rec.startRecording()
        } catch (_: IllegalStateException) {
            rec.release()
            return StartResult.Failed
        }
        record = rec
        pcm = ByteArray(capacity)
        running = true
        thread = Thread(::loop, "vboard-rec").apply { start() }
        return StartResult.Started
    }

    /**
     * Stops capture. Returns the in-memory WAV, or null when the take
     * was shorter than 0.3s. Either way the internal buffer is cleared.
     */
    @Synchronized
    fun stop(): ByteArray? {
        running = false
        joinLoop()
        record?.let {
            try {
                it.stop()
            } catch (_: IllegalStateException) {
                // Already stopped; fall through to release.
            }
            it.release()
        }
        record = null
        val take = frames
        val buf = pcm
        frames = 0
        pcm = ByteArray(0)
        if (WavBuilder.isTooShort(take)) {
            Arrays.fill(buf, 0)
            return null
        }
        val wav = WavBuilder.build(buf, take)
        Arrays.fill(buf, 0)
        return wav
    }

    /** Aborts capture and wipes the RAM buffer. */
    @Synchronized
    fun cancel() {
        running = false
        joinLoop()
        shutDown()
        frames = 0
        val buf = pcm
        pcm = ByteArray(0)
        Arrays.fill(buf, 0)
    }

    /** Full teardown for view destroy. Idempotent. */
    @Synchronized
    fun release() {
        cancel()
    }

    private fun loop() {
        val rec = record ?: return
        val chunk = ShortArray(1024)
        while (running) {
            val read = try {
                rec.read(chunk, 0, chunk.size)
            } catch (_: IllegalStateException) {
                break
            }
            if (read <= 0) continue
            val space = WavBuilder.maxFrames() - frames
            if (space <= 0) break
            val take = read.coerceAtMost(space)
            var peak = 0
            for (i in 0 until take) {
                val s = chunk[i].toInt()
                val a = abs(s)
                if (a > peak) peak = a
                val base = frames * 2 + i * 2
                pcm[base] = (s and 0xFF).toByte()
                pcm[base + 1] = ((s shr 8) and 0xFF).toByte()
            }
            frames += take
            onAmplitude((peak / 32768f * AMPLITUDE_GAIN).coerceIn(0f, 1f))
            if (frames >= WavBuilder.maxFrames()) break
        }
        val hitCap = frames >= WavBuilder.maxFrames()
        running = false
        if (hitCap) onAutoStop()
    }

    private fun joinLoop() {
        val t = thread
        thread = null
        if (t != null && t !== Thread.currentThread()) {
            try {
                t.join(1000)
            } catch (_: InterruptedException) {
                Thread.currentThread().interrupt()
            }
        }
    }

    private fun shutDown() {
        running = false
        joinLoop()
        try {
            record?.release()
        } catch (_: Exception) {
            // Release must never throw out of teardown.
        }
        record = null
    }

    companion object {
        private const val AMPLITUDE_GAIN = 3f
    }
}
