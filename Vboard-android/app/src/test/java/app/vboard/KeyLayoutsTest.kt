package app.vboard

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class KeyLayoutsTest {
    @Test
    fun rows_haveExpectedKeyCounts() {
        assertEquals(10, KeyLayouts.NumberRow.size)
        assertEquals(10, KeyLayouts.RowTop.size)
        assertEquals(9, KeyLayouts.RowMiddle.size)
        assertEquals(7, KeyLayouts.RowBottom.size)
    }

    @Test
    fun letterRows_holdSingleUppercaseLetters() {
        (KeyLayouts.RowTop + KeyLayouts.RowMiddle + KeyLayouts.RowBottom).forEach { key ->
            assertEquals(1, key.length)
            assertTrue(key[0].isUpperCase())
        }
    }

    @Test
    fun spaceLabel_matchesDesignLanguage() {
        assertEquals("English (US)", KeyLayouts.SPACE_LABEL)
    }
}
