from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from whatisplaying.discord import DiscordClient, DiscordError


class _Handler(BaseHTTPRequestHandler):
    def do_PATCH(self) -> None:  # noqa: N802 - HTTP verb
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.server.records.append(  # type: ignore[attr-defined]
            {
                "method": self.command,
                "path": self.path,
                "headers": dict(self.headers),
                "body": body,
            }
        )
        status, payload = self.server.responses.pop(0)  # type: ignore[attr-defined]
        data = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args) -> None:
        pass


class DiscordClientTest(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.server.records = []  # type: ignore[attr-defined]
        self.server.responses = []  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = (
            f"http://127.0.0.1:{self.server.server_address[1]}/users/@me/settings"
        )

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def _respond(self, status: int, payload: str = "{}") -> None:
        self.server.responses.append((status, payload))  # type: ignore[attr-defined]

    def test_update_payload(self) -> None:
        self._respond(200)
        client = DiscordClient("token-123", url=self.url)
        client.update("Song | Artist (=^•ω•^=)")

        self.assertEqual(len(self.server.records), 1)  # type: ignore[attr-defined]
        record = self.server.records[0]  # type: ignore[attr-defined]
        self.assertEqual(record["method"], "PATCH")
        self.assertEqual(record["headers"]["Authorization"], "token-123")
        self.assertEqual(
            json.loads(record["body"]),
            {
                "custom_status": {
                    "text": "Song | Artist (=^•ω•^=)",
                    "emoji_name": "🌱",
                }
            },
        )

    def test_clear_payload(self) -> None:
        self._respond(200)
        DiscordClient("token-123", url=self.url).clear()
        record = self.server.records[0]  # type: ignore[attr-defined]
        self.assertEqual(json.loads(record["body"]), {"custom_status": None})

    def test_empty_token_is_rejected_locally(self) -> None:
        with self.assertRaises(DiscordError):
            DiscordClient("", url=self.url).update("x")
        self.assertEqual(len(self.server.records), 0)  # type: ignore[attr-defined]

    def test_unauthorized_message(self) -> None:
        self._respond(401, '{"message": "401: Unauthorized"}')
        with self.assertRaises(DiscordError) as context:
            DiscordClient("bad", url=self.url).clear()
        self.assertEqual(context.exception.status, 401)
        self.assertIn("401", str(context.exception))
        self.assertIn("Unauthorized", str(context.exception))

    def test_rate_limit_is_retried_once(self) -> None:
        self._respond(429, '{"message": "You are being rate limited", "retry_after": 0}')
        self._respond(200)
        delays: list[float] = []
        client = DiscordClient(
            "token-123", url=self.url, retry_sleep=delays.append
        )
        client.update("Song")
        self.assertEqual(len(self.server.records), 2)  # type: ignore[attr-defined]
        self.assertEqual(delays, [0.25])

    def test_server_error_is_reported(self) -> None:
        self._respond(500, '{"message": "boom"}')
        with self.assertRaises(DiscordError) as context:
            DiscordClient("token", url=self.url).update("Song")
        self.assertEqual(context.exception.status, 500)
        self.assertIn("500", str(context.exception))


if __name__ == "__main__":
    unittest.main()
