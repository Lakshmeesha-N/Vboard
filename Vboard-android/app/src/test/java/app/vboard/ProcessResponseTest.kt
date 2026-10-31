package app.vboard

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ProcessResponseTest {

    @Test
    fun parsesFullInsertResponse() {
        val json = """
            {
              "transcript": "hello world",
              "timing_ms": 1234.5,
              "audio_duration_ms": 2100,
              "action": {"action": "insert", "text": "Hello, world!", "find": null, "which": null},
              "used_fallback": false,
              "note": null,
              "timings_ms": {"stt_ms": 900.0}
            }
        """.trimIndent()
        val resp = ProcessResponseParser.parse(json)
        assertNotNull(resp)
        resp!!
        assertEquals("hello world", resp.transcript)
        assertFalse(resp.usedFallback)
        assertNull(resp.note)
        assertNotNull(resp.action)
        assertEquals("insert", resp.action!!.action)
        assertEquals("Hello, world!", resp.action.text)
        assertNull(resp.action.find)
        assertNull(resp.action.which)
    }

    @Test
    fun parsesReplaceWithFindAndWhich() {
        val json = """
            {"transcript": "fix teh typo", "timing_ms": 10, "audio_duration_ms": 500,
             "action": {"action": "replace", "text": "the", "find": "teh", "which": "first"}}
        """.trimIndent()
        val action = ProcessResponseParser.parse(json)?.action
        assertNotNull(action)
        assertEquals("replace", action!!.action)
        assertEquals("the", action.text)
        assertEquals("teh", action.find)
        assertEquals("first", action.which)
    }

    @Test
    fun parsesRewriteShape() {
        val json = """
            {"transcript": "rewrite all", "timing_ms": 10, "audio_duration_ms": 500,
             "action": {"action": "rewrite", "text": "Clean slate.", "find": null, "which": "all"}}
        """.trimIndent()
        val action = ProcessResponseParser.parse(json)?.action
        assertNotNull(action)
        assertEquals("rewrite", action!!.action)
        assertEquals("Clean slate.", action.text)
        assertEquals("all", action.which)
    }

    @Test
    fun nullActionParsesToNull() {
        val json = """
            {"transcript": "hmm", "timing_ms": 10, "audio_duration_ms": 500, "action": null}
        """.trimIndent()
        val resp = ProcessResponseParser.parse(json)
        assertNotNull(resp)
        assertNull(resp!!.action)
    }

    @Test
    fun missingActionParsesToNull() {
        val resp = ProcessResponseParser.parse(
            """{"transcript": "hmm", "timing_ms": 10, "audio_duration_ms": 500}""",
        )
        assertNotNull(resp)
        assertNull(resp!!.action)
    }

    @Test
    fun usedFallbackAndNoteParsed() {
        val json = """
            {"transcript": "raw words", "timing_ms": 10, "audio_duration_ms": 500,
             "action": {"action": "insert", "text": "raw words"},
             "used_fallback": true, "note": "asr_only"}
        """.trimIndent()
        val resp = ProcessResponseParser.parse(json)
        assertNotNull(resp)
        assertTrue(resp!!.usedFallback)
        assertEquals("asr_only", resp.note)
        assertEquals("raw words", resp.action?.text)
    }

    @Test
    fun unknownActionBecomesNull() {
        val json = """
            {"transcript": "x", "timing_ms": 1, "audio_duration_ms": 100,
             "action": {"action": "shout", "text": "X!"}}
        """.trimIndent()
        val resp = ProcessResponseParser.parse(json)
        assertNotNull(resp)
        assertNull(resp!!.action)
    }

    @Test
    fun actionMissingTextBecomesNull() {
        val json = """
            {"transcript": "x", "timing_ms": 1, "audio_duration_ms": 100,
             "action": {"action": "insert"}}
        """.trimIndent()
        val resp = ProcessResponseParser.parse(json)
        assertNotNull(resp)
        assertNull(resp!!.action)
    }

    @Test
    fun malformedJsonReturnsNull() {
        assertNull(ProcessResponseParser.parse("{oops"))
        assertNull(ProcessResponseParser.parse(""))
        assertNull(ProcessResponseParser.parse("not json at all"))
    }

    @Test
    fun kannadaInsertTextPreserved() {
        val json = """
            {"transcript": "hegiddiri", "timing_ms": 10, "audio_duration_ms": 500,
             "action": {"action": "insert", "text": "ಹೇಗಿದ್ದೀರಿ?"}}
        """.trimIndent()
        val action = ProcessResponseParser.parse(json)?.action
        assertNotNull(action)
        assertEquals("ಹೇಗಿದ್ದೀರಿ?", action!!.text)
    }
}
