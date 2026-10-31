package app.vboard

/** In-memory WAV assembly. Pure Kotlin, no Android imports. */
object WavBuilder {
    const val SAMPLE_RATE = 16000
    const val CHANNELS = 1
    const val BITS_PER_SAMPLE = 16
    const val HEADER_SIZE = 44
    const val MIN_DURATION_MS = 300L
    const val MAX_DURATION_MS = 30_000L
    const val MAX_WAV_BYTES = 5 * 1024 * 1024

    fun minFrames(): Int = (SAMPLE_RATE * MIN_DURATION_MS / 1000).toInt()

    fun maxFrames(): Int = (SAMPLE_RATE * MAX_DURATION_MS / 1000).toInt()

    fun isTooShort(frames: Int): Boolean = frames < minFrames()

    /** PCM byte count for [frames] mono 16-bit frames. Long to avoid overflow. */
    fun pcmBytes(frames: Int): Long = frames.toLong() * (BITS_PER_SAMPLE / 8)

    /**
     * Assembles a complete WAV from the first [frames] frames of [pcm]
     * (little-endian 16-bit mono). Returns a fresh array; [pcm] is untouched.
     */
    fun build(pcm: ByteArray, frames: Int): ByteArray {
        val dataSize = frames * (BITS_PER_SAMPLE / 8)
        require(frames >= 0 && dataSize <= pcm.size) { "frames out of range" }
        val out = ByteArray(HEADER_SIZE + dataSize)
        writeHeader(out, dataSize)
        pcm.copyInto(out, HEADER_SIZE, 0, dataSize)
        return out
    }

    fun writeHeader(out: ByteArray, dataSize: Int) {
        require(out.size >= HEADER_SIZE) { "header buffer too small" }
        val byteRate = SAMPLE_RATE * CHANNELS * BITS_PER_SAMPLE / 8
        val blockAlign = CHANNELS * BITS_PER_SAMPLE / 8
        putString(out, 0, "RIFF")
        putLe32(out, 4, 36 + dataSize)
        putString(out, 8, "WAVE")
        putString(out, 12, "fmt ")
        putLe32(out, 16, 16)
        putLe16(out, 20, 1) // PCM
        putLe16(out, 22, CHANNELS)
        putLe32(out, 24, SAMPLE_RATE)
        putLe32(out, 28, byteRate)
        putLe16(out, 32, blockAlign)
        putLe16(out, 34, BITS_PER_SAMPLE)
        putString(out, 36, "data")
        putLe32(out, 40, dataSize)
    }

    private fun putString(out: ByteArray, offset: Int, value: String) {
        for (i in value.indices) out[offset + i] = value[i].code.toByte()
    }

    private fun putLe16(out: ByteArray, offset: Int, value: Int) {
        out[offset] = (value and 0xFF).toByte()
        out[offset + 1] = ((value shr 8) and 0xFF).toByte()
    }

    private fun putLe32(out: ByteArray, offset: Int, value: Int) {
        out[offset] = (value and 0xFF).toByte()
        out[offset + 1] = ((value shr 8) and 0xFF).toByte()
        out[offset + 2] = ((value shr 16) and 0xFF).toByte()
        out[offset + 3] = ((value shr 24) and 0xFF).toByte()
    }
}
