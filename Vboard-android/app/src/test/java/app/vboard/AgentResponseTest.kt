package app.vboard

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class AgentResponseTest {

    @Test
    fun parsesCleanupResponse() {
        val json = """{"text": "I went to the market yesterday.", "timing_ms": 900.0}"""
        val resp = AgentResponseParser.parse(json)
        assertNotNull(resp)
        resp!!
        assertEquals("I went to the market yesterday.", resp.text)
    }

    @Test
    fun missingTextReturnsNull() {
        assertNull(AgentResponseParser.parse("""{"timing_ms": 5}"""))
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
        val json = """{"text": "ಹೇಗಿದ್ದೀರಿ?", "timing_ms": 10}"""
        val resp = AgentResponseParser.parse(json)
        assertNotNull(resp)
        assertEquals("ಹೇಗಿದ್ದೀರಿ?", resp!!.text)
    }
}
