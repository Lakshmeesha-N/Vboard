package app.vboard.suggest

import org.junit.Assert.assertEquals
import org.junit.Test

class CurrentWordTest {

    @Test
    fun trailingWord_isExtracted() {
        assertEquals("mar", CurrentWord.extract("i went mar"))
    }

    @Test
    fun trailingSpace_meansNoWord() {
        assertEquals("", CurrentWord.extract("hello "))
    }

    @Test
    fun emptyInput_meansNoWord() {
        assertEquals("", CurrentWord.extract(""))
    }

    @Test
    fun punctuation_breaksTheWord() {
        assertEquals("known", CurrentWord.extract("well-known"))
        assertEquals("abc", CurrentWord.extract("price: 42abc"))
        assertEquals("abc", CurrentWord.extract("line1\nabc"))
    }

    @Test
    fun digitsAlone_meanNoWord() {
        assertEquals("", CurrentWord.extract("42"))
    }

    @Test
    fun apostropheInsideWord_isKept() {
        assertEquals("don't", CurrentWord.extract("don don't"))
    }

    @Test
    fun strayApostrophes_areTrimmed() {
        assertEquals("don", CurrentWord.extract("don'"))
        assertEquals("tis", CurrentWord.extract("'tis"))
    }

    @Test
    fun uppercase_isPreservedForDisplay() {
        assertEquals("Mar", CurrentWord.extract("Mar"))
    }
}
