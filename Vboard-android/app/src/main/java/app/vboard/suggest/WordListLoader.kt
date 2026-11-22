package app.vboard.suggest

import java.util.Locale

/**
 * Parses the suggestion word list asset.
 * Pure Kotlin, no Android imports; the caller opens the asset stream.
 */
object WordListLoader {

    /**
     * Parses `word<TAB>rank` lines, rank 1 = most common.
     * Skips blanks, `#` comments, and malformed lines.
     * Deduplicates keeping the best (lowest) rank.
     * Returns entries sorted most-common first.
     */
    fun parse(lines: Sequence<String>): List<WordFreq> {
        val best = LinkedHashMap<String, Int>()
        for (raw in lines) {
            val line = raw.trim()
            if (line.isEmpty() || line.startsWith("#")) continue
            val tab = line.indexOf('\t')
            if (tab <= 0) continue
            val word = line.substring(0, tab).trim().lowercase(Locale.ROOT)
            if (!isIndexable(word)) continue
            val rank = line.substring(tab + 1).trim().toIntOrNull() ?: continue
            if (rank <= 0) continue
            val prev = best[word]
            if (prev == null || rank < prev) best[word] = rank
        }
        return best.map { (word, rank) -> WordFreq(word, rank) }.sortedBy { it.rank }
    }

    private fun isIndexable(word: String): Boolean =
        word.isNotEmpty() && word.all { it in 'a'..'z' || it == '\'' }
}
