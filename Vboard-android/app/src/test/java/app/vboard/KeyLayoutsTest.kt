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

    @Test
    fun rowMiddle_startsWithAWithoutShift() {
        assertEquals("A", KeyLayouts.RowMiddle.first())
        KeyLayouts.RowMiddle.forEach { key ->
            assertTrue(key != KeyLayouts.KEY_SHIFT)
            assertTrue(key != KeyLayouts.SHIFT_LABEL)
            assertTrue(key != KeyLayouts.CAPS_LABEL)
        }
    }

    @Test
    fun applyCaps_togglesLetterCase() {
        assertEquals("A", KeyLayouts.applyCaps("a", true))
        assertEquals("a", KeyLayouts.applyCaps("A", false))
        assertEquals("A", KeyLayouts.applyCaps("A", true))
    }

    @Test
    fun applyCaps_leavesNonLettersAlone() {
        assertEquals(",", KeyLayouts.applyCaps(",", true))
        assertEquals(" ", KeyLayouts.applyCaps(" ", true))
        assertEquals("?123", KeyLayouts.applyCaps("?123", true))
    }

    @Test
    fun enterBehavior_multiLineAlwaysNewLine() {
        // Ids mirror EditorInfo.IME_ACTION_*: 0 = UNSPECIFIED, 2 = GO, 6 = DONE.
        assertEquals(KeyLayouts.EnterBehavior.NEW_LINE, KeyLayouts.decideEnterBehavior(true, 0))
        assertEquals(KeyLayouts.EnterBehavior.NEW_LINE, KeyLayouts.decideEnterBehavior(true, 2))
        assertEquals(KeyLayouts.EnterBehavior.NEW_LINE, KeyLayouts.decideEnterBehavior(true, 6))
    }

    @Test
    fun enterBehavior_singleLineActionTriesEditorAction() {
        // 2 = GO, 3 = SEARCH, 4 = SEND, 5 = NEXT, 6 = DONE, 7 = PREVIOUS.
        listOf(2, 3, 4, 5, 6, 7).forEach { action ->
            assertEquals(KeyLayouts.EnterBehavior.EDITOR_ACTION, KeyLayouts.decideEnterBehavior(false, action))
        }
    }

    @Test
    fun enterBehavior_singleLineWithoutActionSendsKeyEvent() {
        // 0 = UNSPECIFIED, 1 = NONE.
        assertEquals(KeyLayouts.EnterBehavior.KEY_EVENT, KeyLayouts.decideEnterBehavior(false, 0))
        assertEquals(KeyLayouts.EnterBehavior.KEY_EVENT, KeyLayouts.decideEnterBehavior(false, 1))
    }
}
