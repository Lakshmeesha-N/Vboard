package app.vboard.suggest

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SuggesterTest {

    private val words = listOf(
        WordFreq("the", 1),
        WordFreq("that", 10),
        WordFreq("then", 50),
        WordFreq("they", 60),
        WordFreq("zebra", 20000),
    )

    @Test
    fun commonWords_rankBeforeRareOnes() {
        assertEquals(listOf("the", "that", "then"), Suggester(words).suggest("th"))
    }

    @Test
    fun exactWord_comesFirst() {
        assertEquals(listOf("the", "then", "they"), Suggester(words).suggest("the"))
    }

    @Test
    fun limit_capsResultCount() {
        assertEquals(2, Suggester(words).suggest("th", 2).size)
        assertEquals(listOf("the", "that"), Suggester(words).suggest("th", 2))
    }

    @Test
    fun prefix_isCaseInsensitive() {
        assertEquals(Suggester(words).suggest("th"), Suggester(words).suggest("TH"))
    }

    @Test
    fun unknownPrefix_returnsEmpty() {
        assertTrue(Suggester(words).suggest("qx").isEmpty())
    }

    @Test
    fun blankPrefix_returnsEmpty() {
        assertTrue(Suggester(words).suggest("").isEmpty())
        assertTrue(Suggester(words).suggest("   ").isEmpty())
    }

    @Test
    fun nonLetterPrefix_returnsEmpty() {
        assertTrue(Suggester(words).suggest("th3").isEmpty())
        assertTrue(Suggester(words).suggest("42").isEmpty())
    }

    @Test
    fun zeroLimit_returnsEmpty() {
        assertTrue(Suggester(words).suggest("th", 0).isEmpty())
    }

    @Test
    fun apostropheWords_matchPlainPrefix() {
        val s = Suggester(listOf(WordFreq("don't", 100), WordFreq("donut", 500)))
        assertEquals(listOf("don't", "donut"), s.suggest("don"))
        assertEquals(listOf("don't"), s.suggest("don't"))
    }

    @Test
    fun duplicates_keepBestRank() {
        val s = Suggester(listOf(WordFreq("then", 5000), WordFreq("the", 1), WordFreq("then", 50)))
        assertEquals(listOf("the", "then"), s.suggest("the"))
        assertEquals(2, s.size)
    }

    @Test
    fun invalidWords_areSkipped() {
        val s = Suggester(
            listOf(
                WordFreq("", 1),
                WordFreq("hello!", 2),
                WordFreq("naïve", 3),
                WordFreq("ok", 4),
            ),
        )
        assertEquals(1, s.size)
        assertEquals(listOf("ok"), s.suggest("o"))
    }
}
