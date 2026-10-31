package app.vboard

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ContextPolicyTest {

    // EditorInfo class/variation bits (mirrored; see ContextPolicy).
    private fun type(cls: Int, variation: Int) = cls or variation
    private val text = 0x00000001
    private val number = 0x00000002
    private val phone = 0x00000003
    private val variationPassword = 0x00000080
    private val variationVisiblePassword = 0x00000090
    private val variationWebPassword = 0x000000e0
    private val numberVariationPassword = 0x00000010
    private val variationEmail = 0x00000020

    @Test
    fun passwordFieldsDetected() {
        assertTrue(ContextPolicy.isPasswordInputType(type(text, variationPassword)))
        assertTrue(ContextPolicy.isPasswordInputType(type(text, variationVisiblePassword)))
        assertTrue(ContextPolicy.isPasswordInputType(type(text, variationWebPassword)))
        assertTrue(ContextPolicy.isPasswordInputType(type(number, numberVariationPassword)))
    }

    @Test
    fun plainFieldsNotPasswords() {
        assertFalse(ContextPolicy.isPasswordInputType(type(text, 0)))
        assertFalse(ContextPolicy.isPasswordInputType(type(text, variationEmail)))
        assertFalse(ContextPolicy.isPasswordInputType(type(number, 0)))
        assertFalse(ContextPolicy.isPasswordInputType(type(phone, 0)))
        assertFalse(ContextPolicy.isPasswordInputType(0))
    }

    @Test
    fun shortContextUnchanged() {
        assertEquals("hello world", ContextPolicy.capContext("hello ", "world", 10_000))
        assertEquals("", ContextPolicy.capContext(null, null, 10_000))
        assertEquals("a", ContextPolicy.capContext(null, "a", 10_000))
    }

    @Test
    fun longContextKeepsCursorNeighborhood() {
        val before = "B".repeat(8_000)
        val after = "A".repeat(8_000)
        val out = ContextPolicy.capContext(before, after, 10_000)
        assertEquals(10_000, out.length)
        // Before-text first (tail of `before`), then the head of `after`.
        assertEquals("B".repeat(5_000), out.take(5_000))
        assertEquals("A".repeat(5_000), out.takeLast(5_000))
    }

    @Test
    fun leftoverGoesToBefore() {
        val out = ContextPolicy.capContext("B".repeat(9_999), "xyz", 10_000)
        assertEquals(10_000, out.length)
        assertTrue(out.endsWith("xyz"))
        assertEquals("B".repeat(9_997) + "xyz", out)
    }

    @Test
    fun kannadaContextSurvivesCap() {
        val kannada = "ಹೇಗಿದ್ದೀರಿ ".repeat(1_000)
        val out = ContextPolicy.capContext(kannada, "end", 100)
        assertEquals(100, out.length)
        assertTrue(out.endsWith("end"))
    }
}
