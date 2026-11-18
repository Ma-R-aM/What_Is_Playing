from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, Signal

from whatisplaying.config import Config, ConfigStore
from whatisplaying.controller import Controller
from whatisplaying.media import PlayerSnapshot


def make_player(
    *,
    status: str = "Playing",
    title: str = "Song",
    artist: str = "Artist",
    key: str = "spotify",
    identity: str = "Spotify",
) -> PlayerSnapshot:
    return PlayerSnapshot(
        bus_name=f"org.mpris.MediaPlayer2.{key}",
        key=key,
        identity=identity,
        desktop_entry=key,
        playback_status=status,
        title=title,
        artist=artist,
        album="Album",
        track_id="/track/1",
    )


class FakeMonitor:
    available = True

    def __init__(self) -> None:
        self.players: list[PlayerSnapshot] = []
        self.error = ""

    def refresh(self) -> list[PlayerSnapshot]:
        return list(self.players)


class FakeWorker(QObject):
    updated = Signal(str, str)
    cleared = Signal()
    failed = Signal(str, str, str, float, int)

    def __init__(self) -> None:
        super().__init__()
        self.jobs: list[tuple] = []
        self.stopped = False

    def submit_update(self, token: str, text: str, key: str) -> None:
        self.jobs.append(("update", token, text, key))

    def submit_clear(self, token: str) -> None:
        self.jobs.append(("clear", token, None, ""))

    def stop(self) -> None:
        self.stopped = True

    def finish_update(self) -> None:
        action, token, text, key = self.jobs[-1]
        assert action == "update"
        self.updated.emit(key, text)

    def finish_clear(self) -> None:
        self.cleared.emit()


class ControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ConfigStore(Path(self.tmp.name) / "config.json")
        self.monitor = FakeMonitor()
        self.worker = FakeWorker()
        self.config = Config(token="token", enabled=True)
        self.controller = Controller(
            self.store,
            self.config,
            monitor=self.monitor,  # type: ignore[arg-type]
            worker=self.worker,  # type: ignore[arg-type]
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_playing_sends_status_once(self) -> None:
        self.monitor.players = [make_player()]
        self.controller.refresh(force=True)
        self.assertEqual(len(self.worker.jobs), 1)
        action, token, text, key = self.worker.jobs[0]
        self.assertEqual(action, "update")
        self.assertEqual(token, "token")
        self.assertIn("Song | Artist", text)
        self.assertEqual(self.controller.pending_send_key, key)

        self.worker.finish_update()
        self.assertTrue(self.controller.status_shown)

        self.controller.refresh()
        self.assertEqual(len(self.worker.jobs), 1)

    def test_pause_clears_and_resume_restores(self) -> None:
        self.monitor.players = [make_player()]
        self.controller.refresh(force=True)
        self.worker.finish_update()

        self.monitor.players = [make_player(status="Paused")]
        self.controller.refresh()
        self.assertEqual(len(self.worker.jobs), 2)
        self.assertEqual(self.worker.jobs[1][0], "clear")
        self.worker.finish_clear()
        self.assertFalse(self.controller.status_shown)

        self.monitor.players = [make_player()]
        self.controller.refresh()
        self.assertEqual(len(self.worker.jobs), 3)
        self.assertEqual(self.worker.jobs[2][0], "update")

    def test_changed_track_sends_again(self) -> None:
        self.monitor.players = [make_player(title="First")]
        self.controller.refresh(force=True)
        self.worker.finish_update()

        self.monitor.players = [make_player(title="Second")]
        self.controller.refresh()
        self.assertEqual(len(self.worker.jobs), 2)
        self.assertIn("Second", self.worker.jobs[1][2])

    def test_no_token_does_not_send(self) -> None:
        self.config.token = ""
        self.monitor.players = [make_player()]
        self.controller.refresh(force=True)
        self.assertEqual(self.worker.jobs, [])

    def test_disabled_does_not_send(self) -> None:
        self.config.enabled = False
        self.monitor.players = [make_player()]
        self.controller.refresh(force=True)
        self.assertEqual(self.worker.jobs, [])

    def test_selected_players_filter(self) -> None:
        self.config.selected_players = ["vlc"]
        self.monitor.players = [make_player(key="spotify")]
        self.controller.refresh(force=True)
        self.assertEqual(self.worker.jobs, [])
        self.assertIsNone(self.controller.active)

        self.monitor.players = [make_player(key="vlc", identity="VLC")]
        self.controller.refresh(force=True)
        self.assertEqual(len(self.worker.jobs), 1)

    def test_failure_sets_retry_cooldown(self) -> None:
        self.monitor.players = [make_player()]
        self.controller.refresh(force=True)
        key = self.worker.jobs[0][3]
        self.worker.failed.emit("update", key, "Discord returned HTTP 500.", 0.0, 500)
        self.assertIsNone(self.controller.pending_send_key)
        self.assertGreater(self.controller.retry_at, 0)

        self.controller.refresh()
        self.assertEqual(len(self.worker.jobs), 1)
        self.controller.refresh(force=True)
        self.assertEqual(len(self.worker.jobs), 2)

    def test_kaomoji_toggle_resends(self) -> None:
        self.monitor.players = [make_player()]
        self.controller.refresh(force=True)
        self.worker.finish_update()

        self.controller.set_append_kaomoji(False)
        self.assertEqual(len(self.worker.jobs), 2)
        self.assertNotIn("(=^", self.worker.jobs[1][2])

    def test_failure_keeps_track_of_existing_status(self) -> None:
        self.monitor.players = [make_player(title="First")]
        self.controller.refresh(force=True)
        self.worker.finish_update()

        self.monitor.players = [make_player(title="Second")]
        self.controller.refresh()
        failed_key = self.worker.jobs[-1][3]
        self.worker.failed.emit("update", failed_key, "Discord returned HTTP 500.", 0.0, 500)

        # The first track may still be on Discord, so pausing must clear it
        # even though the newest update failed.
        self.monitor.players = [make_player(status="Paused", title="Second")]
        self.controller.refresh(force=True)
        self.assertEqual(self.worker.jobs[-1][0], "clear")

    def test_test_status_is_restored_to_current_track(self) -> None:
        self.monitor.players = [make_player()]
        self.controller.refresh(force=True)
        self.worker.finish_update()

        self.controller.test_status()
        self.assertEqual(self.worker.jobs[-1][0], "update")
        self.assertEqual(self.worker.jobs[-1][3], "__whatisplaying_test__")
        self.worker.finish_update()

        self.assertGreaterEqual(len(self.worker.jobs), 3)
        self.assertEqual(self.worker.jobs[-1][0], "update")
        self.assertNotEqual(self.worker.jobs[-1][3], "__whatisplaying_test__")
        self.assertIn("Song | Artist", self.worker.jobs[-1][2])

    def test_status_cleared_when_player_disappears(self) -> None:
        self.monitor.players = [make_player()]
        self.controller.refresh(force=True)
        self.worker.finish_update()

        self.monitor.players = []
        self.controller.refresh()
        self.assertEqual(self.worker.jobs[-1][0], "clear")

    def test_shutdown_clears_only_if_shown(self) -> None:
        self.monitor.players = [make_player()]
        self.controller.refresh(force=True)
        self.worker.finish_update()
        self.controller.shutdown()
        self.assertEqual(self.worker.jobs[-1][0], "clear")
        self.assertTrue(self.worker.stopped)


if __name__ == "__main__":
    unittest.main()
