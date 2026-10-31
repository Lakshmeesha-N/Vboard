package app.vboard

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class WavBuilderTest {

    @Test
    fun headerHasRiffWaveMarkers() {
        val out = ByteArray(WavBuilder.HEADER_SIZE)
        WavBuilder.writeHeader(out, 0)
        assertEquals("RIFF", out.slice(0..3).map { it.toInt().toChar() }.joinToString(""))
        assertEquals("WAVE", out.slice(8..11).map { it.toInt().toChar() }.joinToString(""))
        assertEquals("fmt ", out.slice(12..15).map { it.toInt().toChar() }.joinToString(""))
        assertEquals("data", out.slice(36..39).map { it.toInt().toChar() }.joinToString(""))
    }

    @Test
    fun headerDescribes16kMonoPcm16() {
        val out = ByteArray(WavBuilder.HEADER_SIZE)
        WavBuilder.writeHeader(out, 32000)
        fun le16(at: Int) = (out[at].toInt() and 0xFF) or ((out[at + 1].toInt() and 0xFF) shl 8)
        fun le32(at: Int) = (out[at].toInt() and 0xFF) or
            ((out[at + 1].toInt() and 0xFF) shl 8) or
            ((out[at + 2].toInt() and 0xFF) shl 16) or
            ((out[at + 3].toInt() and 0xFF) shl 24)
        assertEquals(1, le16(20))
        assertEquals(1, le16(22))
        assertEquals(16000, le32(24))
        assertEquals(32000, le32(28))
        assertEquals(2, le16(32))
        assertEquals(16, le16(34))
        assertEquals(36 + 32000, le32(4))
        assertEquals(32000, le32(40))
    }

    @Test
    fun buildPrependsHeaderAndCopiesFrames() {
        val pcm = ByteArray(32) { it.toByte() }
        val wav = WavBuilder.build(pcm, 8)
        assertEquals(WavBuilder.HEADER_SIZE + 16, wav.size)
        assertArrayEquals(pcm.slice(0..15).toByteArray(), wav.slice(44..59).toByteArray())
    }

    @Test
    fun durationLimits() {
        assertEquals(4800, WavBuilder.minFrames())
        assertEquals(480000, WavBuilder.maxFrames())
        assertTrue(WavBuilder.isTooShort(4799))
        assertFalse(WavBuilder.isTooShort(4800))
        // 30s at 16k mono 16-bit stays far under the 5 MB contract cap.
        assertTrue(WavBuilder.HEADER_SIZE + WavBuilder.pcmBytes(WavBuilder.maxFrames()) < WavBuilder.MAX_WAV_BYTES)
    }
}
