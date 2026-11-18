"""Minimal Discord client for updating the current user's custom status."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from contextlib import suppress

log = logging.getLogger(__name__)

SETTINGS_URL = "https://discord.com/api/v9/users/@me/settings"
STATUS_EMOJI = "🌱"
USER_AGENT = "WhatIsPlaying/1.0"


class DiscordError(RuntimeError):
    """A Discord request failed in a way worth showing to the user."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retry_after: float = 0.0,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def endpoint() -> str:
    """Allow tests and power users to point the app at another endpoint."""
    return os.environ.get("WHATISPLAYING_DISCORD_URL", SETTINGS_URL)


def _error_message(status: int, body: str) -> tuple[str, float]:
    retry_after = 0.0
    discord_message = ""
    with suppress(ValueError, TypeError):
        parsed = json.loads(body)
        if isinstance(parsed, dict):
            if isinstance(parsed.get("message"), str):
                discord_message = parsed["message"]
            if isinstance(parsed.get("retry_after"), (int, float)):
                retry_after = max(0.0, float(parsed["retry_after"]))

    if status == 401:
        base = "Discord rejected the token (401 Unauthorized). Check the token and try again."
    elif status == 403:
        base = "Discord refused the request (403 Forbidden). The token may be restricted."
    elif status == 429:
        base = "Discord rate-limited the update (429)."
    else:
        base = f"Discord returned HTTP {status}."

    if discord_message and discord_message.strip():
        base += f" {discord_message.strip()}"
    return base, retry_after


class DiscordClient:
    def __init__(
        self,
        token: str,
        *,
        url: str | None = None,
        timeout: float = 10.0,
        retry_sleep=time.sleep,
    ) -> None:
        self.token = token.strip()
        self.url = url or endpoint()
        self.timeout = timeout
        self._retry_sleep = retry_sleep

    def update(self, text: str) -> None:
        if not text.strip():
            raise DiscordError("Refusing to send an empty Discord status.")
        payload = {
            "custom_status": {
                "text": text,
                "emoji_name": STATUS_EMOJI,
            }
        }
        self._request(payload, "update")

    def clear(self) -> None:
        self._request({"custom_status": None}, "clear")

    def _request(self, payload: dict, action: str) -> None:
        if not self.token:
            raise DiscordError("Discord token is not set.")

        attempt = 0
        while True:
            try:
                self._perform(payload)
                return
            except DiscordError as exc:
                # Retry a rate limit once, after Discord's requested delay.
                if (
                    exc.status == 429
                    and attempt == 0
                    and exc.retry_after <= 10.0
                ):
                    attempt += 1
                    delay = max(exc.retry_after, 0.25)
                    log.warning("Discord rate limit; retrying in %.1fs", delay)
                    self._retry_sleep(delay)
                    continue
                raise
            except Exception as exc:  # noqa: BLE001 - surface a friendly message
                raise DiscordError(
                    f"Could not reach Discord while trying to {action}: {exc}"
                ) from exc

    def _perform(self, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.url,
            data=data,
            method="PATCH",
            headers={
                "Authorization": self.token,
                "Content-Type": "application/json;charset=UTF-8",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                response.read()
                return
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")
            finally:
                exc.close()
            message, retry_after = _error_message(exc.code, body)
            raise DiscordError(
                message, status=exc.code, retry_after=retry_after
            ) from exc
        except urllib.error.URLError as exc:
            raise DiscordError(f"Network error: {exc.reason}") from exc
