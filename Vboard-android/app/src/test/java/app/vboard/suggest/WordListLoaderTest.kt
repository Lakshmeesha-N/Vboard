package app.vboard.suggest

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class WordListLoaderTest {

    @Test
    fun parsesWordTabRank_sortedByRank() {
        val out = WordListLoader.parse(
            sequenceOf("then\t50", "the\t1", "that\t10"),
        )
        assertEquals(
            listOf(WordFreq("the", 1), WordFreq("that", 10), WordFreq("then", 50)),
            out,
        )
    }

    @Test
    fun skipsBlanksCommentsAndMalformedLines() {
        val out = WordListLoader.parse(
            sequenceOf(
                "",
                "   ",
                "# top words",
                "the 1",
                "then\tnot-a-number",
                "that\t0",
                "than\t-3",
                "\t7",
                "ok\t4",
            ),
        )
        assertEquals(listOf(WordFreq("ok", 4)), out)
    }

    @Test
    fun duplicates_keepBestRank() {
        val out = WordListLoader.parse(sequenceOf("then\t5000", "then\t50"))
        assertEquals(listOf(WordFreq("then", 50)), out)
    }

    @Test
    fun uppercasedWords_areLowercased() {
        val out = WordListLoader.parse(sequenceOf("The\t1"))
        assertEquals(listOf(WordFreq("the", 1)), out)
    }

    @Test
    fun nonAsciiWords_areSkipped() {
        val out = WordListLoader.parse(sequenceOf("naïve\t3", "ok\t4"))
        assertEquals(listOf(WordFreq("ok", 4)), out)
    }

    @Test
    fun emptyInput_returnsEmpty() {
        assertTrue(WordListLoader.parse(emptySequence()).isEmpty())
    }
}
