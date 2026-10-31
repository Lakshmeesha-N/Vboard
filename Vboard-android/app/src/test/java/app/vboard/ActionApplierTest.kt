package app.vboard

import org.junit.Assert.assertEquals
import org.junit.Test

class ActionApplierTest {

    private fun action(kind: String, text: String) = ActionModel(kind, text, null, null)

    @Test
    fun insertAppendsText() {
        val out = ActionApplier.applyAction("hello", action("insert", " world"))
        assertEquals("hello world", out.newText)
        assertEquals(ActionApplier.Outcome.INSERTED, out.outcome)
    }

    @Test
    fun rewriteReplacesEverything() {
        val out = ActionApplier.applyAction("old mess", action("rewrite", "clean text"))
        assertEquals("clean text", out.newText)
        assertEquals(ActionApplier.Outcome.REWRITTEN, out.outcome)
    }

    @Test
    fun rewriteKannadaText() {
        val out = ActionApplier.applyAction("ಹಳೆಯ ಪಠ್ಯ", action("rewrite", "ಹೇಗಿದ್ದೀರಿ"))
        assertEquals("ಹೇಗಿದ್ದೀರಿ", out.newText)
        assertEquals(ActionApplier.Outcome.REWRITTEN, out.outcome)
    }

    @Test
    fun rewriteEmptyBox() {
        val out = ActionApplier.applyAction("", action("rewrite", "ಹೊಸ ಪಠ್ಯ"))
        assertEquals("ಹೊಸ ಪಠ್ಯ", out.newText)
        assertEquals(ActionApplier.Outcome.REWRITTEN, out.outcome)
    }

    @Test
    fun equalTextMeansNothingChanged() {
        val out = ActionApplier.applyAction("same", action("rewrite", "same"))
        assertEquals("same", out.newText)
        assertEquals(ActionApplier.Outcome.NOTHING_CHANGED, out.outcome)
    }

    @Test
    fun replaceIsUnsupportedStub() {
        val out = ActionApplier.applyAction("box", action("replace", "new"))
        assertEquals("box", out.newText)
        assertEquals(ActionApplier.Outcome.REPLACE_UNSUPPORTED, out.outcome)
    }

    @Test
    fun tooLongBoxNeverRewrites() {
        val big = "x".repeat(ContextPolicy.CONTEXT_MAX_CHARS + 1)
        assertEquals(true, ActionApplier.isTooLong(big))
        assertEquals(false, ActionApplier.isTooLong("short"))
        val out = ActionApplier.applyAction(big, action("rewrite", "new"))
        assertEquals(big, out.newText)
        assertEquals(ActionApplier.Outcome.TOO_LONG, out.outcome)
    }

    @Test
    fun nullActionChangesNothing() {
        val out = ActionApplier.applyAction("box", null)
        assertEquals("box", out.newText)
        assertEquals(ActionApplier.Outcome.NULL_ACTION, out.outcome)
    }
}
