package app.vboard

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MinimizePolicyTest {

    @Test
    fun enterAllowedWhenIdle() {
        assertTrue(MinimizePolicy.canEnter(recording = false, sending = false))
    }

    @Test
    fun enterBlockedWhileRecording() {
        assertFalse(MinimizePolicy.canEnter(recording = true, sending = false))
    }

    @Test
    fun enterBlockedWhileSending() {
        assertFalse(MinimizePolicy.canEnter(recording = false, sending = true))
    }

    @Test
    fun cancelEnabledOnlyWhileRecording() {
        assertTrue(MinimizePolicy.isCancelEnabled(recording = true))
        assertFalse(MinimizePolicy.isCancelEnabled(recording = false))
    }

    @Test
    fun clampKeepsPillInsideScreen() {
        assertEquals(50 to 60, MinimizePolicy.clampPosition(50, 60, 300, 500))
        assertEquals(0 to 0, MinimizePolicy.clampPosition(-10, -20, 300, 500))
        assertEquals(300 to 500, MinimizePolicy.clampPosition(999, 999, 300, 500))
    }

    @Test
    fun clampWithNoRoomPinsToZero() {
        assertEquals(0 to 0, MinimizePolicy.clampPosition(50, 60, -5, -5))
    }

    @Test
    fun recordingBarGrowsLeftFromIdlePill() {
        assertEquals(700, MinimizePolicy.anchorRecordingLeft(1000, 300, 900))
        assertEquals(0, MinimizePolicy.anchorRecordingLeft(200, 300, 900))
        assertEquals(500, MinimizePolicy.anchorRecordingLeft(1000, 300, 500))
    }

    @Test
    fun flipTogglesOrientationBothWays() {
        assertEquals(
            MinimizePolicy.Orientation.HORIZONTAL,
            MinimizePolicy.flipped(MinimizePolicy.Orientation.VERTICAL),
        )
        assertEquals(
            MinimizePolicy.Orientation.VERTICAL,
            MinimizePolicy.flipped(MinimizePolicy.Orientation.HORIZONTAL),
        )
    }

    @Test
    fun pillStateFollowsThePipeline() {
        assertEquals(MinimizePolicy.PillState.IDLE, MinimizePolicy.pillState(false, false))
        assertEquals(MinimizePolicy.PillState.RECORDING, MinimizePolicy.pillState(true, false))
        assertEquals(MinimizePolicy.PillState.PROCESSING, MinimizePolicy.pillState(false, true))
        assertEquals(MinimizePolicy.PillState.RECORDING, MinimizePolicy.pillState(true, true))
    }
}
