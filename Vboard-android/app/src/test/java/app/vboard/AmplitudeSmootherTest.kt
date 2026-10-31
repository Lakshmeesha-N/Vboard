package app.vboard

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AmplitudeSmootherTest {

    @Test
    fun risesTowardSustainedInputWithoutJumping() {
        val smoother = AmplitudeSmoother()
        val first = smoother.update(1f)
        assertTrue(first > 0f && first < 1f)
        repeat(20) { smoother.update(1f) }
        assertTrue(smoother.value > 0.99f)
    }

    @Test
    fun decaysTowardSilence() {
        val smoother = AmplitudeSmoother()
        repeat(20) { smoother.update(1f) }
        repeat(20) { smoother.update(0f) }
        assertTrue(smoother.value < 0.01f)
    }

    @Test
    fun clampsOutOfRangeInput() {
        val smoother = AmplitudeSmoother()
        smoother.update(5f)
        assertTrue(smoother.value <= 1f)
        smoother.reset()
        smoother.update(-3f)
        assertEquals(0f, smoother.value, 0f)
    }

    @Test
    fun resetClearsValue() {
        val smoother = AmplitudeSmoother()
        smoother.update(1f)
        smoother.reset()
        assertEquals(0f, smoother.value, 0f)
    }
}
