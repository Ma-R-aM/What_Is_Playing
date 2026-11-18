from __future__ import annotations

import unittest

from whatisplaying.parser import (
    KAOMOJIS,
    build_status,
    clean_artist,
    clean_title,
    is_player_notification,
)


class CleanArtistTest(unittest.TestCase):
    def test_play_count_variants(self) -> None:
        cases = {
            "IamOutlandish a 1,3 tis. prehraní": "IamOutlandish",
            "IamOutlandish, 1,3 tis. prehraní": "IamOutlandish",
            "IamOutlandish • 1,3 tis. prehraní": "IamOutlandish",
            "Artist, 1.3K plays": "Artist",
            "Artist, 12K views": "Artist",
            "Artist One, Artist Two a 1,3 tis. prehraní": "Artist One, Artist Two",
            "Artist, 1 234 zobrazení": "Artist",
            "Umělec, 2,5 mil. zhlédnutí": "Umělec",
            "Artist - 3 listens": "Artist",
            "Artist | 1,3 tis. prehratí": "Artist",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(clean_artist(raw), expected)

    def test_number_in_name_is_kept(self) -> None:
        self.assertEqual(clean_artist("Blink-182"), "Blink-182")
        self.assertEqual(clean_artist("The 1975"), "The 1975")
        self.assertEqual(clean_artist("2Pac"), "2Pac")

    def test_trailing_separator_is_removed(self) -> None:
        self.assertEqual(clean_artist("Artist — 1.3K plays"), "Artist")

    def test_non_breaking_spaces(self) -> None:
        self.assertEqual(
            clean_artist("Artist, 1\u00a0234\u202fzobrazení"), "Artist"
        )


class CleanTitleTest(unittest.TestCase):
    def test_with_credits_are_removed(self) -> None:
        self.assertEqual(clean_title("Song (with Somebody)"), "Song")
        self.assertEqual(clean_title("Pieseň (spolu s Niekým)"), "Pieseň")

    def test_plain_title_is_kept(self) -> None:
        self.assertEqual(clean_title("  Normal Song  "), "Normal Song")


class BuildStatusTest(unittest.TestCase):
    def test_status_format(self) -> None:
        self.assertEqual(
            build_status("Song", "Artist", kaomoji="(=^•ω•^=)"),
            "Song | Artist (=^•ω•^=)",
        )

    def test_missing_artist(self) -> None:
        self.assertEqual(
            build_status("Song", "", kaomoji="(test)"), "Song (test)"
        )

    def test_truncation_respects_limit(self) -> None:
        status = build_status("x" * 200, "y" * 50, kaomoji="(test)")
        self.assertLessEqual(len(status), 128)
        self.assertTrue(status.endswith("... (test)"))

    def test_kaomoji_can_be_disabled(self) -> None:
        self.assertEqual(
            build_status("Song", "Artist", append_kaomoji=False),
            "Song | Artist",
        )

    def test_kaomoji_list_is_not_empty(self) -> None:
        self.assertGreater(len(KAOMOJIS), 20)
        self.assertTrue(all(k.startswith("(") for k in KAOMOJIS))


class PlayerNotificationTest(unittest.TestCase):
    def test_music_player_titles(self) -> None:
        self.assertTrue(is_player_notification("Music player"))
        self.assertTrue(is_player_notification("Prehrávač hudby"))
        self.assertTrue(is_player_notification("Metrolist"))
        self.assertFalse(is_player_notification("Song name"))


if __name__ == "__main__":
    unittest.main()
