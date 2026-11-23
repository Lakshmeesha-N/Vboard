package app.vboard.suggest

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SuggestionControllerTest {

    private val assetText = "the\t1\nthat\t9\nthen\t57\nzebra\t20000\n"

    private fun controller(
        shown: MutableList<List<String>>,
        text: String = assetText,
    ): SuggestionController {
        val scope = kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.Unconfined)
        return SuggestionController(
            scope = scope,
            openWordList = { text.byteInputStream() },
            onSuggestions = { shown += it },
        )
    }

    private fun loaded(): Pair<SuggestionController, MutableList<List<String>>> {
        val shown = mutableListOf<List<String>>()
        val c = controller(shown)
        runBlocking { c.start(); c.loadJob?.join() }
        shown.clear()
        return c to shown
    }

    @Test
    fun refresh_suggestsAfterLoad() {
        val (c, shown) = loaded()
        c.onCommitted("the", password = false, idle = true)
        assertEquals(listOf(listOf("the", "then")), shown)
    }

    @Test
    fun refresh_hidesWhenNotIdle() {
        val (c, shown) = loaded()
        c.onCommitted("the", password = false, idle = false)
        assertEquals(listOf(emptyList<String>()), shown)
    }

    @Test
    fun refresh_hidesForPassword() {
        val (c, shown) = loaded()
        c.onCommitted("the", password = true, idle = true)
        assertEquals(listOf(emptyList<String>()), shown)
    }

    @Test
    fun refresh_hidesForNullOrEmptyWord() {
        val (c, shown) = loaded()
        c.onCommitted(null, password = false, idle = true)
        c.onCommitted("", password = false, idle = true)
        assertEquals(listOf(emptyList(), emptyList<String>()), shown)
    }

    @Test
    fun refresh_beforeLoad_hidesWithoutBlocking() {
        val shown = mutableListOf<List<String>>()
        val c = controller(shown)
        c.onCommitted("the", password = false, idle = true)
        assertEquals(listOf(emptyList<String>()), shown)
    }

    @Test
    fun refresh_loadFailure_hides() {
        val shown = mutableListOf<List<String>>()
        val scope = kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.Unconfined)
        val c = SuggestionController(
            scope = scope,
            openWordList = { null },
            onSuggestions = { shown += it },
        )
        runBlocking { c.start(); c.loadJob?.join() }
        c.onCommitted("the", password = false, idle = true)
        assertEquals(listOf(emptyList<String>()), shown)
    }

    @Test
    fun pick_lowercaseWord_addsTrailingSpace() {
        val (c, _) = loaded()
        assertEquals("hello ", c.buildReplacement("hel", "hello"))
    }

    @Test
    fun pick_initialCaps_isPreserved() {
        val (c, _) = loaded()
        assertEquals("Hello ", c.buildReplacement("Hel", "hello"))
    }

    @Test
    fun pick_emptyCurrent_leavesSuggestionAsIs() {
        val (c, _) = loaded()
        assertEquals("hello ", c.buildReplacement("", "hello"))
    }

    @Test
    fun start_isIdempotent() {
        val (c, shown) = loaded()
        val first = c.loadJob
        c.start()
        assertTrue(c.loadJob === first)
        assertTrue(shown.isEmpty())
    }
}
