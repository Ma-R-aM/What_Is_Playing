from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from whatisplaying.config import Config, ConfigStore
from whatisplaying.controller import Controller
from whatisplaying.media import PlayerSnapshot


class _Handler(BaseHTTPRequestHandler):
    def do_PATCH(self) -> None:  # noqa: N802 - HTTP verb
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length))
        self.server.records.append(body)  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *args) -> None:
        pass


class _Monitor:
    available = True
    error = ""

    def __init__(self) -> None:
        self.players = [
            PlayerSnapshot(
                bus_name="org.mpris.MediaPlayer2.spotify",
                key="spotify",
                identity="Spotify",
                desktop_entry="spotify",
                playback_status="Playing",
                title="Song",
                artist="Artist",
                album="Album",
                track_id="/track/1",
            )
        ]

    def refresh(self) -> list[PlayerSnapshot]:
        return list(self.players)


class WorkerIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.server.records = []  # type: ignore[attr-defined]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{self.server.server_address[1]}/settings"
        self.env = mock.patch.dict(
            os.environ, {"WHATISPLAYING_DISCORD_URL": url}, clear=False
        )
        self.env.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.monitor = _Monitor()
        self.controller = Controller(
            ConfigStore(Path(self.tmp.name) / "config.json"),
            Config(token="token", enabled=True),
            monitor=self.monitor,  # type: ignore[arg-type]
        )

    def tearDown(self) -> None:
        self.controller.shutdown()
        self.env.stop()
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def _wait_for(self, predicate, timeout_ms: int = 3000) -> None:
        elapsed = 0
        while not predicate() and elapsed < timeout_ms:
            loop = QEventLoop()
            QTimer.singleShot(50, loop.quit)
            loop.exec()
            elapsed += 50
        self.assertTrue(predicate(), "condition was not met before timeout")

    def test_update_then_clear_round_trip(self) -> None:
        self.controller.refresh(force=True)
        self._wait_for(lambda: len(self.server.records) == 1)  # type: ignore[attr-defined]
        self._wait_for(lambda: self.controller.status_shown)
        payload = self.server.records[0]  # type: ignore[attr-defined]
        self.assertIn("Song | Artist", payload["custom_status"]["text"])

        self.monitor.players[0] = PlayerSnapshot(
            bus_name="org.mpris.MediaPlayer2.spotify",
            key="spotify",
            identity="Spotify",
            desktop_entry="spotify",
            playback_status="Paused",
            title="Song",
            artist="Artist",
            album="Album",
            track_id="/track/1",
        )
        self.controller.refresh()
        self._wait_for(lambda: len(self.server.records) == 2)  # type: ignore[attr-defined]
        self.assertIsNone(self.server.records[1]["custom_status"])  # type: ignore[attr-defined]
        self._wait_for(lambda: not self.controller.status_shown)


if __name__ == "__main__":
    unittest.main()
