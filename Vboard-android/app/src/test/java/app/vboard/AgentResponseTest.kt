package app.vboard

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AgentResponseTest {

    @Test
    fun parsesCleanupResponse() {
        val json = """{"text": "I went to the market yesterday.", "used_search": false, "rounds": 1, "note": null, "timing_ms": 900.0}"""
        val resp = AgentResponseParser.parse(json)
        assertNotNull(resp)
        resp!!
        assertEquals("I went to the market yesterday.", resp.text)
        assertFalse(resp.usedSearch)
        assertEquals(1, resp.rounds)
        assertNull(resp.note)
    }

    @Test
    fun parsesOutOfScopeNote() {
        val json = """{"text": "This task is beyond my current capabilities.", "used_search": false, "rounds": 1, "note": "out_of_scope", "timing_ms": 100.0}"""
        val resp = AgentResponseParser.parse(json)
        assertNotNull(resp)
        assertEquals("out_of_scope", resp!!.note)
    }

    @Test
    fun missingTextReturnsNull() {
        assertNull(AgentResponseParser.parse("""{"used_search": false, "rounds": 1, "timing_ms": 5}"""))
    }

    @Test
    fun malformedReturnsNull() {
        assertNull(AgentResponseParser.parse("{oops"))
        assertNull(AgentResponseParser.parse(""))
    }

    @Test
    fun parses422DetailMessage() {
        val json = """{"detail": [{"loc": ["body", "content"], "msg": "Content too long", "type": "value_error"}]}"""
        assertEquals("Content too long", AgentResponseParser.parseErrorDetail(json))
    }

    @Test
    fun bad422BodyReturnsNull() {
        assertNull(AgentResponseParser.parseErrorDetail("{oops"))
        assertNull(AgentResponseParser.parseErrorDetail("""{"other": 1}"""))
    }

    @Test
    fun kannadaTextPreserved() {
        val json = """{"text": "ಹೇಗಿದ್ದೀರಿ?", "used_search": false, "rounds": 1, "note": null, "timing_ms": 10}"""
        val resp = AgentResponseParser.parse(json)
        assertNotNull(resp)
        assertEquals("ಹೇಗಿದ್ದೀರಿ?", resp!!.text)
        assertTrue(resp.rounds == 1)
    }
}
