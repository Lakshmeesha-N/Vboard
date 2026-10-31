package app.vboard

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
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
    fun enterBehavior_searchActionRunsEvenWhenMultiLine() {
        // 3 = SEARCH; editor action wins over the multi-line flag.
        assertEquals(KeyLayouts.EnterBehavior.EDITOR_ACTION, KeyLayouts.decideEnterBehavior(true, 3, false))
        assertEquals(KeyLayouts.EnterBehavior.EDITOR_ACTION, KeyLayouts.decideEnterBehavior(false, 3, false))
    }

    @Test
    fun enterBehavior_singleLineActionTriesEditorAction() {
        // 2 = GO, 3 = SEARCH, 4 = SEND, 5 = NEXT, 6 = DONE, 7 = PREVIOUS.
        listOf(2, 3, 4, 5, 6, 7).forEach { action ->
            assertEquals(KeyLayouts.EnterBehavior.EDITOR_ACTION, KeyLayouts.decideEnterBehavior(false, action, false))
        }
    }

    @Test
    fun enterBehavior_noActionMultiLineGivesNewLine() {
        // 0 = UNSPECIFIED, 1 = NONE.
        assertEquals(KeyLayouts.EnterBehavior.NEW_LINE, KeyLayouts.decideEnterBehavior(true, 0, false))
        assertEquals(KeyLayouts.EnterBehavior.NEW_LINE, KeyLayouts.decideEnterBehavior(true, 1, false))
    }

    @Test
    fun enterBehavior_singleLineWithoutActionSendsKeyEvent() {
        assertEquals(KeyLayouts.EnterBehavior.KEY_EVENT, KeyLayouts.decideEnterBehavior(false, 0, false))
        assertEquals(KeyLayouts.EnterBehavior.KEY_EVENT, KeyLayouts.decideEnterBehavior(false, 1, false))
    }

    @Test
    fun enterBehavior_noEnterActionFlagAlwaysNewLine() {
        // IME_FLAG_NO_ENTER_ACTION set: newline regardless of action or shape.
        assertEquals(KeyLayouts.EnterBehavior.NEW_LINE, KeyLayouts.decideEnterBehavior(false, 2, true))
        assertEquals(KeyLayouts.EnterBehavior.NEW_LINE, KeyLayouts.decideEnterBehavior(true, 2, true))
        assertEquals(KeyLayouts.EnterBehavior.NEW_LINE, KeyLayouts.decideEnterBehavior(false, 0, true))
    }

    @Test
    fun repeatTiming_firstTickWaitsThenRepeatsFast() {
        assertEquals(400L, KeyLayouts.RepeatTiming.delayForTick(0))
        assertEquals(50L, KeyLayouts.RepeatTiming.delayForTick(1))
        assertEquals(50L, KeyLayouts.RepeatTiming.delayForTick(100))
    }

    @Test
    fun repeatTiming_stopsWhenTextboxEmpty() {
        assertTrue(KeyLayouts.RepeatTiming.shouldContinue(true))
        assertFalse(KeyLayouts.RepeatTiming.shouldContinue(false))
    }
}
