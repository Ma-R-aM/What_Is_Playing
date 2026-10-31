package martin_svk.whatisplaying

import org.junit.Assert.assertEquals
import org.junit.Test

class TrackInfoParserTest {

    @Test
    fun `removes Slovak play count joined with a`() {
        assertEquals(
            "IamOutlandish",
            TrackInfoParser.cleanArtist("IamOutlandish a 1,3 tis. prehraní")
        )
    }

    @Test
    fun `removes Slovak play count joined with comma`() {
        assertEquals(
            "IamOutlandish",
            TrackInfoParser.cleanArtist("IamOutlandish, 1,3 tis. prehraní")
        )
    }

    @Test
    fun `handles non-breaking spaces`() {
        assertEquals(
            "Artist",
            TrackInfoParser.cleanArtist("Artist a 1,3\u00A0tis.\u00A0prehraní")
        )
    }

    @Test
    fun `removes play count with bullet separator`() {
        assertEquals(
            "IamOutlandish",
            TrackInfoParser.cleanArtist("IamOutlandish • 1,3 tis. prehraní")
        )
    }

    @Test
    fun `removes English play count`() {
        assertEquals(
            "Artist",
            TrackInfoParser.cleanArtist("Artist, 1.3K plays")
        )
    }

    @Test
    fun `removes views count`() {
        assertEquals(
            "Artist",
            TrackInfoParser.cleanArtist("Artist, 12K views")
        )
    }

    @Test
    fun `keeps multiple artists`() {
        assertEquals(
            "Artist One, Artist Two",
            TrackInfoParser.cleanArtist("Artist One, Artist Two a 1,3 tis. prehraní")
        )
    }

    @Test
    fun `does not remove numbers from a normal artist name`() {
        assertEquals(
            "Blink-182",
            TrackInfoParser.cleanArtist("Blink-182")
        )
    }

    @Test
    fun `cleans with credits from title`() {
        assertEquals(
            "Song",
            TrackInfoParser.cleanTitle("Song (with Somebody)")
        )
    }
}
