package app.vboard.suggest

import java.io.InputStream
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Owns English word suggestions: lazy-loads the word list off the main
 * thread, answers per-keystroke queries from memory, and builds tap
 * replacements. No autocorrect, no learning, no network.
 * All [onSuggestions] calls fire on the scope's thread.
 */
class SuggestionController(
    private val scope: CoroutineScope,
    private val openWordList: () -> InputStream?,
    private val onSuggestions: (List<String>) -> Unit,
) {

    internal var loadJob: Job? = null
    private var suggester: Suggester? = null

    /** Idempotent; safe to call on every input view start. */
    fun start() {
        if (suggester != null || loadJob?.isActive == true) return
        loadJob = scope.launch {
            val words = withContext(Dispatchers.IO) {
                try {
                    openWordList()?.use { stream ->
                        WordListLoader.parse(stream.bufferedReader().lineSequence())
                    }
                } catch (_: Exception) {
                    null
                }
            } ?: return@launch
            if (words.isNotEmpty()) suggester = Suggester(words)
        }
    }

    fun hide() {
        onSuggestions(emptyList())
    }

    /**
     * Refresh after a commit or cursor move. Shows suggestions only for a
     * real word in an idle, non-password box; hides otherwise. Never blocks:
     * an unloaded dictionary simply hides until the load finishes.
     */
    fun onCommitted(word: String?, password: Boolean, idle: Boolean) {
        if (!idle || password) {
            hide()
            return
        }
        val current = suggester
        if (word.isNullOrEmpty() || current == null) {
            hide()
            return
        }
        onSuggestions(current.suggest(word))
    }

    /**
     * Replacement for a tapped suggestion: keeps the typed initial capital,
     * then a trailing space so typing continues uninterrupted.
     */
    fun buildReplacement(current: String, suggestion: String): String {
        val base =
            if (current.isNotEmpty() && suggestion.isNotEmpty() && current[0].isUpperCase()) {
                suggestion.replaceFirstChar { it.uppercaseChar() }
            } else {
                suggestion
            }
        return "$base "
    }
}
