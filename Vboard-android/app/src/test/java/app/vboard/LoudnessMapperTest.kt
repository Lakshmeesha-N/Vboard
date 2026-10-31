package app.vboard

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class LoudnessMapperTest {

    @Test
    fun silenceMapsNearZero() {
        val mapper = LoudnessMapper()
        assertEquals(0f, mapper.map(0f), 0f)
        assertEquals(0f, mapper.map(0.005f), 0.001f)
        assertEquals(0f, mapper.map(0.02f), 0.001f)
    }

    @Test
    fun normalSpeechLandsMidBand() {
        val mapper = LoudnessMapper()
        val soft = mapper.map(0.1f)
        val firm = mapper.map(0.15f)
        assertTrue("soft speech $soft should be ~0.5", soft > 0.4f && soft < 0.6f)
        assertTrue("firm speech $firm should be ~0.8", firm > 0.7f && firm < 0.9f)
    }

    @Test
    fun loudInputClampsAtOne() {
        val mapper = LoudnessMapper()
        assertEquals(1f, mapper.map(0.5f), 0f)
        assertEquals(1f, mapper.map(1f), 0f)
    }

    @Test
    fun risesFast() {
        val mapper = LoudnessMapper()
        val first = mapper.update(0.15f)
        assertTrue("first update $first should jump near target", first > 0.4f)
    }

    @Test
    fun fallsSlowerThanRise() {
        val mapper = LoudnessMapper()
        repeat(10) { mapper.update(0.15f) }
        val before = mapper.value
        mapper.update(0f)
        val drop = before - mapper.value
        assertTrue("single silent update should shed little: dropped $drop", drop < 0.25f)
        repeat(30) { mapper.update(0f) }
        assertTrue(mapper.value < 0.01f)
    }

    @Test
    fun resetClearsValue() {
        val mapper = LoudnessMapper()
        mapper.update(0.15f)
        mapper.reset()
        assertEquals(0f, mapper.value, 0f)
    }
}
