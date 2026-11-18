from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from whatisplaying import smtc


class _Operation:
    def __init__(self, value) -> None:
        self.value = value

    def get(self):
        return self.value


class _Session:
    def __init__(
        self,
        app_id: str,
        status: str,
        *,
        title: str = "",
        artist: str = "",
        album: str = "",
        number: int = 0,
    ) -> None:
        self.source_app_user_model_id = app_id
        self._status = status
        self._properties = SimpleNamespace(
            title=title,
            artist=artist,
            album_title=album,
            track_number=number,
        )

    def get_playback_info(self):
        return SimpleNamespace(playback_status=self._status)

    def try_get_media_properties_async(self):
        return _Operation(self._properties)


class _Manager:
    def __init__(self, sessions) -> None:
        self._sessions = list(sessions)

    def get_sessions(self):
        return list(self._sessions)


_STATUS = SimpleNamespace(PLAYING="playing", PAUSED="paused", STOPPED="stopped")


def _control(sessions):
    return SimpleNamespace(
        GlobalSystemMediaTransportControlsSessionManager=SimpleNamespace(
            request_async=lambda: _Operation(_Manager(sessions))
        ),
        GlobalSystemMediaTransportControlsSessionPlaybackStatus=_STATUS,
    )


class DescribeAppTest(unittest.TestCase):
    def test_known_packaged_app(self) -> None:
        key, identity = smtc.describe_app(
            "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"
        )
        self.assertEqual(key, "spotifyab.spotifymusic_zpdnekdrzrea0!spotify")
        self.assertEqual(identity, "Spotify")

    def test_known_executable(self) -> None:
        self.assertEqual(smtc.describe_app("chrome.exe"), ("chrome", "Google Chrome"))

    def test_browser_profile_variants_collapse(self) -> None:
        self.assertEqual(
            smtc.describe_app("MSEdge.127.0.0.1_example.com.Default"),
            ("msedge", "Microsoft Edge"),
        )
        self.assertEqual(
            smtc.describe_app("Chrome.Default"), ("chrome", "Google Chrome")
        )
        self.assertEqual(
            smtc.describe_app("Firefox.Profile 2"), ("firefox", "Firefox")
        )

    def test_unknown_app_is_humanized(self) -> None:
        _key, identity = smtc.describe_app(r"C:\Apps\SomeNewPlayer.exe")
        self.assertEqual(identity, "Some New Player")

    def test_empty_app_id(self) -> None:
        self.assertEqual(smtc.describe_app(""), ("unknown", "Media player"))


class StatusNameTest(unittest.TestCase):
    def test_known_enum_values(self) -> None:
        self.assertEqual(smtc._status_name("playing", _STATUS), "Playing")
        self.assertEqual(smtc._status_name("paused", _STATUS), "Paused")
        self.assertEqual(smtc._status_name("stopped", _STATUS), "Stopped")

    def test_name_fallback_and_closed(self) -> None:
        self.assertEqual(
            smtc._status_name(SimpleNamespace(name="Playing"), _STATUS), "Playing"
        )
        self.assertEqual(
            smtc._status_name(SimpleNamespace(name="Closed"), _STATUS), "Stopped"
        )


class WindowsMediaMonitorTest(unittest.TestCase):
    def test_poll_reads_sessions_and_prefers_playing(self) -> None:
        sessions = [
            _Session("spotify.exe", "paused", title="Old", artist="A"),
            _Session("spotify.exe", "playing", title="Song", artist="Artist", number=3),
            _Session("vlc.exe", "stopped", title="", artist=""),
        ]
        monitor = smtc.WindowsMediaMonitor(control=_control(sessions))

        players = monitor.poll_once()

        self.assertTrue(monitor.available)
        self.assertEqual(len(players), 1)
        player = players[0]
        self.assertEqual(player.identity, "Spotify")
        self.assertEqual(player.playback_status, "Playing")
        self.assertEqual(player.title, "Song")
        self.assertEqual(player.artist, "Artist")
        self.assertEqual(player.track_id, "track:3")

    def test_broken_session_is_skipped(self) -> None:
        broken = _Session("broken.exe", "playing", title="x")
        broken.get_playback_info = mock.Mock(side_effect=RuntimeError("closed"))
        monitor = smtc.WindowsMediaMonitor(
            control=_control([broken, _Session("vlc.exe", "playing", title="Good")])
        )

        players = monitor.poll_once()

        self.assertEqual([player.title for player in players], ["Good"])

    def test_missing_winrt_is_reported(self) -> None:
        with mock.patch.object(
            smtc, "_load_control_module", side_effect=ImportError("no winrt")
        ):
            monitor = smtc.WindowsMediaMonitor()

        self.assertFalse(monitor.available)
        self.assertIn("requirements-windows.txt", monitor.error)
        self.assertEqual(monitor.refresh(), [])


if __name__ == "__main__":
    unittest.main()
