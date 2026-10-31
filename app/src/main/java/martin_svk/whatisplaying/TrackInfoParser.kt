package martin_svk.whatisplaying

/**
 * Cleans up the raw title/artist strings that music apps put into their
 * media notifications.
 */
object TrackInfoParser {

    private val withSlovakRegex = Regex("""\(spolu s[^)]*\)""", RegexOption.IGNORE_CASE)
    private val withEnglishRegex = Regex("""\(with[^)]*\)""", RegexOption.IGNORE_CASE)

    /**
     * Matches a trailing play-count/views suffix such as:
     *
     *   IamOutlandish a 1,3 tis. prehraní
     *   IamOutlandish, 1,3 tis. prehraní
     *   Artist • 1.3K plays
     *   Artist, 1 234 zobrazení
     *
     * It intentionally requires a play-count/views word at the end, so artist
     * names that merely contain a number are left alone.
     */
    private val playCountRegex = Regex(
        """(?i)\s*(?:[,•·|&–—-]\s*|\ba\s+)?""" +
            """(?:\d{1,3}(?:[ \u00A0\u202F]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)""" +
            """\s*(?:tis\.?|mil\.?|mld\.?|k|m|b|tisíc|tisic|milión\w*|milion\w*|miliárd\w*|miliard\w*)?""" +
            """\s*(?:prehraní|prehratí|prehrání|přehrání|prehrania|zhliadnutí|zhliadnutia|zhliadnuťia|zhlédnutí|zhlédnutia|plays?|zobrazení|zobrazení|views?|listens?)\s*$"""
    )

    private val trailingSeparators = charArrayOf(',', '•', '·', '|', '&', '-', '–', '—')

    fun cleanTitle(raw: String): String {
        var title = normalize(raw)
        title = withSlovakRegex.replace(title, "")
        title = withEnglishRegex.replace(title, "")
        return title.trim()
    }

    fun cleanArtist(raw: String): String {
        var artist = normalize(raw)
        artist = playCountRegex.replace(artist, "")
        return artist.trim().trimEnd(*trailingSeparators).trim()
    }

    fun isPlayerNotification(title: String): Boolean {
        val normalized = normalize(title)
        return normalized.equals("Prehrávač hudby", ignoreCase = true) ||
            normalized.equals("Music player", ignoreCase = true) ||
            normalized.contains("Metrolist", ignoreCase = true)
    }

    private fun normalize(text: String): String = text
        .replace('\u00A0', ' ')
        .replace('\u202F', ' ')
        .trim()
}
