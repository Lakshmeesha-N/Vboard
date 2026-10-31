package app.vboard

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LanguageListTest {
    @Test
    fun all_holds25ExactNames() {
        assertEquals(25, LanguageList.ALL.size)
        assertTrue(LanguageList.ALL.contains("Mandarin Chinese"))
        assertTrue(LanguageList.ALL.contains("Kannada"))
    }

    @Test
    fun pickerOrder_pinsTopThreeThenAlphabeticalRest() {
        val order = LanguageList.pickerOrder()
        assertEquals(listOf("Kannada", "Hindi", "English"), order.take(3))
        assertEquals(LanguageList.ALL.sorted().filter { it !in LanguageList.PINNED }, order.drop(3))
    }

    @Test
    fun toggle_preservesPickOrder() {
        val sel = LanguageList.toggle(LanguageList.toggle(emptyList(), "Hindi"), "Kannada")
        assertEquals(listOf("Hindi", "Kannada"), sel)
    }

    @Test
    fun toggle_removesOnSecondTap() {
        assertEquals(emptyList<String>(), LanguageList.toggle(listOf("Hindi"), "Hindi"))
    }

    @Test
    fun toggle_ignoresSixthAndUnknown() {
        val full = listOf("Kannada", "Hindi", "English", "Tamil", "Telugu")
        assertEquals(full, LanguageList.toggle(full, "Marathi"))
        assertEquals(emptyList<String>(), LanguageList.toggle(emptyList(), "Klingon"))
    }

    @Test
    fun isValid_requiresOneToFiveKnown() {
        assertFalse(LanguageList.isValid(emptyList()))
        assertTrue(LanguageList.isValid(listOf("Kannada")))
        assertTrue(LanguageList.isValid(listOf("Kannada", "Hindi", "English", "Tamil", "Telugu")))
        assertFalse(LanguageList.isValid(listOf("Kannada", "Hindi", "English", "Tamil", "Telugu", "Thai")))
        assertFalse(LanguageList.isValid(listOf("Klingon")))
    }

    @Test
    fun format_joinsWithCommaNoSpaces() {
        assertEquals("Kannada,Hindi,English", LanguageList.format(listOf("Kannada", "Hindi", "English")))
    }

    @Test
    fun parse_handlesNullBlankAndNoise() {
        assertEquals(emptyList<String>(), LanguageList.parse(null))
        assertEquals(emptyList<String>(), LanguageList.parse("  "))
        assertEquals(
            listOf("Kannada", "English"),
            LanguageList.parse("Kannada, English,English,Klingon")
        )
    }

    @Test
    fun hasLanguages_falseUntilValidSave() {
        assertFalse(LanguageList.hasLanguages(null))
        assertFalse(LanguageList.hasLanguages(""))
        assertFalse(LanguageList.hasLanguages("Kannada,Hindi,English,Tamil,Telugu,Thai"))
        assertTrue(LanguageList.hasLanguages("Kannada,English"))
    }
}
