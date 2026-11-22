package app.vboard.suggest

import java.util.Locale

/** One dictionary entry. Lower rank = more common. */
data class WordFreq(val word: String, val rank: Int)

/**
 * In-memory prefix suggester over a static word list.
 * Built once at load; [suggest] allocates only its result list.
 * Pure Kotlin, no Android imports.
 */
class Suggester(words: List<WordFreq>) {

    private val root = Node()

    /** Distinct words accepted into the trie. */
    val size: Int

    init {
        var count = 0
        // First write wins, so insert best-ranked first.
        words.sortedBy { it.rank }.forEach { (raw, rank) ->
            val word = raw.lowercase(Locale.ROOT)
            if (!isIndexable(word)) return@forEach
            var node = root
            for (c in word) {
                node = node.children.getOrPut(c) { Node() }
            }
            if (node.word == null) {
                node.word = word
                node.rank = rank
                count++
            }
        }
        size = count
    }

    /**
     * Up to [limit] words starting with [prefix], most common first.
     * Returns empty for a blank or non-letter prefix.
     */
    fun suggest(prefix: String, limit: Int = SUGGESTION_LIMIT): List<String> {
        if (limit <= 0) return emptyList()
        val key = prefix.lowercase(Locale.ROOT)
        if (key.isEmpty() || !key.all { isWordChar(it) }) return emptyList()
        var node = root
        for (c in key) {
            node = node.children[c] ?: return emptyList()
        }
        val found = ArrayList<WordFreq>()
        collect(node, found)
        found.sortBy { it.rank }
        return found.take(limit).map { it.word }
    }

    private fun collect(node: Node, out: MutableList<WordFreq>) {
        node.word?.let { out.add(WordFreq(it, node.rank)) }
        for (child in node.children.values) collect(child, out)
    }

    private class Node {
        val children = LinkedHashMap<Char, Node>()
        var word: String? = null
        var rank: Int = Int.MAX_VALUE
    }

    companion object {
        const val SUGGESTION_LIMIT = 3

        private fun isWordChar(c: Char): Boolean =
            c in 'a'..'z' || c == '\''

        private fun isIndexable(word: String): Boolean =
            word.isNotEmpty() && word.all { isWordChar(it) }
    }
}
