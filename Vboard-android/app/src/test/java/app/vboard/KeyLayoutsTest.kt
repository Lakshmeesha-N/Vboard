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
    fun spaceLabel_isBlank() {
        assertEquals("", KeyLayouts.SPACE_LABEL)
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
    fun symbolRows_mirrorLetterRowCounts() {
        assertEquals(KeyLayouts.RowTop.size, KeyLayouts.SymbolRowTop.size)
        assertEquals(KeyLayouts.RowMiddle.size, KeyLayouts.SymbolRowMiddle.size)
        assertEquals(KeyLayouts.RowBottom.size, KeyLayouts.SymbolRowBottom.size)
    }

    @Test
    fun symbolKeys_passThroughCapsAndIncludeAt() {
        assertTrue(KeyLayouts.SymbolRowTop.contains("@"))
        (KeyLayouts.SymbolRowTop + KeyLayouts.SymbolRowMiddle + KeyLayouts.SymbolRowBottom).forEach { key ->
            assertEquals(key, KeyLayouts.applyCaps(key, true))
            assertEquals(key, KeyLayouts.applyCaps(key, false))
        }
        assertEquals("ABC", KeyLayouts.KEY_ABC)
        assertEquals("?123", KeyLayouts.KEY_SYMBOLS)
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

    @Test
    fun shiftTap_offArmsOneShot() {
        assertEquals(KeyLayouts.ShiftState.SINGLE, KeyLayouts.nextShiftState(KeyLayouts.ShiftState.OFF, false))
        assertEquals(KeyLayouts.ShiftState.SINGLE, KeyLayouts.nextShiftState(KeyLayouts.ShiftState.OFF, true))
    }

    @Test
    fun shiftTap_slowSecondTapDisarms() {
        assertEquals(KeyLayouts.ShiftState.OFF, KeyLayouts.nextShiftState(KeyLayouts.ShiftState.SINGLE, false))
    }

    @Test
    fun shiftTap_fastSecondTapLocksCaps() {
        assertEquals(KeyLayouts.ShiftState.CAPS, KeyLayouts.nextShiftState(KeyLayouts.ShiftState.SINGLE, true))
    }

    @Test
    fun shiftTap_capsAlwaysDisarms() {
        assertEquals(KeyLayouts.ShiftState.OFF, KeyLayouts.nextShiftState(KeyLayouts.ShiftState.CAPS, false))
        assertEquals(KeyLayouts.ShiftState.OFF, KeyLayouts.nextShiftState(KeyLayouts.ShiftState.CAPS, true))
    }

    @Test
    fun shiftShowsUppercase_armedAndLocked() {
        assertFalse(KeyLayouts.shiftShowsUppercase(KeyLayouts.ShiftState.OFF))
        assertTrue(KeyLayouts.shiftShowsUppercase(KeyLayouts.ShiftState.SINGLE))
        assertTrue(KeyLayouts.shiftShowsUppercase(KeyLayouts.ShiftState.CAPS))
    }

    @Test
    fun sentenceNeedsCaps_emptyBoxAndFreshLine() {
        assertTrue(KeyLayouts.sentenceNeedsCaps(""))
        assertTrue(KeyLayouts.sentenceNeedsCaps("hello\n"))
    }

    @Test
    fun sentenceNeedsCaps_afterSentencePunctuation() {
        assertTrue(KeyLayouts.sentenceNeedsCaps("hi. "))
        assertTrue(KeyLayouts.sentenceNeedsCaps("really?  "))
        assertTrue(KeyLayouts.sentenceNeedsCaps("wow!\" "))
        assertTrue(KeyLayouts.sentenceNeedsCaps("ok… "))
    }

    @Test
    fun sentenceNeedsCaps_midSentenceStaysLower() {
        assertFalse(KeyLayouts.sentenceNeedsCaps("hel"))
        assertFalse(KeyLayouts.sentenceNeedsCaps("hi."))
        assertFalse(KeyLayouts.sentenceNeedsCaps("hi there "))
        assertFalse(KeyLayouts.sentenceNeedsCaps("3.14"))
    }
}
