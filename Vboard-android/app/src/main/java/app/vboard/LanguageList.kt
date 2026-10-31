package app.vboard

object LanguageList {
    const val MIN_SELECTION = 1
    const val MAX_SELECTION = 5

    val PINNED = listOf("Kannada", "Hindi", "English")

    val ALL = listOf(
        "Arabic", "Bengali", "Dutch", "English", "French",
        "German", "Hebrew", "Hindi", "Indonesian", "Italian",
        "Japanese", "Kannada", "Korean", "Malay", "Mandarin Chinese",
        "Marathi", "Polish", "Portuguese", "Spanish", "Tagalog",
        "Tamil", "Telugu", "Thai", "Turkish", "Vietnamese"
    )

    fun pickerOrder(): List<String> =
        PINNED + ALL.filter { it !in PINNED }.sorted()

    fun toggle(current: List<String>, name: String): List<String> {
        if (name !in ALL) return current
        if (name in current) return current - name
        if (current.size >= MAX_SELECTION) return current
        return current + name
    }

    fun isValid(selection: List<String>): Boolean =
        selection.size in MIN_SELECTION..MAX_SELECTION && selection.all { it in ALL }

    fun format(selection: List<String>): String = selection.joinToString(",")

    fun parse(csv: String?): List<String> {
        if (csv.isNullOrBlank()) return emptyList()
        return csv.split(",").map { it.trim() }.filter { it in ALL }.distinct()
    }

    fun hasLanguages(csv: String?): Boolean = isValid(parse(csv))
}
