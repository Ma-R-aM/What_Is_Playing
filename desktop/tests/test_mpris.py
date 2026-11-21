from __future__ import annotations

import unittest

from whatisplaying.mpris import PLAYER_IFACE, _MprisPlayer


class FakeProperties:
    def __init__(self, metadata=None, error: Exception | None = None) -> None:
        self.metadata = metadata
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def Get(self, interface: str, name: str, timeout: float | None = None):
        self.calls.append((interface, name))
        if self.error is not None:
            raise self.error
        return self.metadata


class FakePlayerInterface:
    def __init__(
        self,
        *,
        status: str = "Playing",
        metadata=None,
        valid: bool = True,
    ) -> None:
        self.status = status
        self.metadata = metadata
        self.valid = valid

    def property(self, name: str):
        if name == "PlaybackStatus":
            return self.status
        if name == "Metadata":
            return self.metadata
        return None

    def isValid(self) -> bool:
        return self.valid


def make_mpris_player(properties: FakeProperties) -> _MprisPlayer:
    player = _MprisPlayer.__new__(_MprisPlayer)
    player.bus_name = "org.mpris.MediaPlayer2.metrolist"
    player.bus = None
    player._properties = properties
    # Qt returns None for complex a{sv} properties, which is the behaviour
    # that caused the "Playing but no song" bug.
    player.player = FakePlayerInterface(metadata=None)
    player.identity = "Metrolist"
    player.desktop_entry = "metrolist"
    player.key = "metrolist"
    player._title = ""
    player._artist = ""
    player._album = ""
    player._track_id = ""
    player._playback_status = ""
    player._metadata_error = ""
    return player


class MprisMetadataTest(unittest.TestCase):
    def test_metadata_is_read_through_dbus_properties(self) -> None:
        properties = FakeProperties(
            {
                "xesam:title": "Come Home",
                "xesam:artist": ["Jace June"],
                "xesam:album": "Come Home",
                "mpris:trackid": "/dev/nucleusframework/track/12",
            }
        )
        player = make_mpris_player(properties)

        snapshot = player.refresh()

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.title, "Come Home")
        self.assertEqual(snapshot.artist, "Jace June")
        self.assertEqual(snapshot.album, "Come Home")
        self.assertEqual(snapshot.track_id, "/dev/nucleusframework/track/12")
        self.assertTrue(snapshot.is_playing)
        self.assertEqual(properties.calls, [(PLAYER_IFACE, "Metadata")])

    def test_falls_back_to_qt_metadata_when_dbus_fails(self) -> None:
        properties = FakeProperties(error=RuntimeError("property unavailable"))
        player = make_mpris_player(properties)
        player.player = FakePlayerInterface(
            metadata={"xesam:title": "Fallback", "xesam:artist": "Artist"}
        )

        snapshot = player.refresh()

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.title, "Fallback")
        self.assertEqual(snapshot.artist, "Artist")

    def test_missing_metadata_still_reports_playing(self) -> None:
        properties = FakeProperties({})
        player = make_mpris_player(properties)

        snapshot = player.refresh()

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.title, "")
        self.assertTrue(snapshot.is_playing)
        self.assertEqual(snapshot.display_status, "Playing")


if __name__ == "__main__":
    unittest.main()
