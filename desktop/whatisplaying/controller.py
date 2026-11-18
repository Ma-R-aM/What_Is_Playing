"""Application controller: media session -> cleaned track -> Discord status."""

from __future__ import annotations

import logging
import queue
import time
from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from .config import Config, ConfigStore
from .discord import DiscordClient, DiscordError
from .media import (
    MediaMonitor,
    PlayerSnapshot,
    create_monitor,
    player_name,
    players_name,
)
from .parser import build_status, clean_artist, clean_title

log = logging.getLogger(__name__)

POLL_INTERVAL_MS = 2000
TEST_KEY = "__whatisplaying_test__"


def track_key_for(player: PlayerSnapshot) -> str:
    return f"{player.key}\x00{player.title}\x00{player.artist}"


@dataclass(frozen=True)
class AppState:
    enabled: bool
    token_configured: bool
    players: tuple[PlayerSnapshot, ...]
    selected_players: tuple[str, ...] | None
    active: PlayerSnapshot | None
    phase: str
    message: str
    last_error: str
    monitor_error: str
    status_text: str = ""


class DiscordWorker(QThread):
    """Serialized network worker so the GUI never blocks on Discord."""

    updated = Signal(str, str)
    cleared = Signal()
    failed = Signal(str, str, str, float, int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._jobs: queue.Queue[tuple | None] = queue.Queue()

    def submit_update(self, token: str, text: str, track_key: str) -> None:
        self._jobs.put(("update", token, text, track_key))

    def submit_clear(self, token: str) -> None:
        self._jobs.put(("clear", token, None, ""))

    def stop(self) -> None:
        self._jobs.put(None)
        self.wait(15_000)

    def run(self) -> None:  # noqa: D401 - Qt entry point
        while True:
            job = self._jobs.get()
            if job is None:
                return

            action, token, text, key = job
            try:
                client = DiscordClient(token)
                if action == "update":
                    client.update(text or "")
                    self.updated.emit(key, text or "")
                else:
                    client.clear()
                    self.cleared.emit()
            except DiscordError as exc:
                self.failed.emit(
                    action,
                    key,
                    str(exc),
                    max(0.0, exc.retry_after),
                    int(exc.status or 0),
                )
            except Exception as exc:  # noqa: BLE001 - keep the worker alive
                log.exception("Unexpected Discord worker failure")
                self.failed.emit(action, key, f"Unexpected error: {exc}", 0.0, 0)


class Controller(QObject):
    state_changed = Signal(object)
    activity = Signal(str, str)

    def __init__(
        self,
        config_store: ConfigStore,
        config: Config,
        monitor: MediaMonitor | None = None,
        worker: DiscordWorker | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.store = config_store
        self.config = config
        self.monitor = monitor or create_monitor()
        self.worker = worker or DiscordWorker(self)
        self.worker.updated.connect(self._on_updated)
        self.worker.cleared.connect(self._on_cleared)
        self.worker.failed.connect(self._on_failed)
        start_worker = getattr(self.worker, "start", None)
        if callable(start_worker):
            start_worker()

        self.players: tuple[PlayerSnapshot, ...] = ()
        self._known_players: dict[str, str] = {}
        self._initial_player_scan = False
        self._monitor_error = ""
        self.status_shown = False
        self.discord_has_status = False
        self.pending_send_key: str | None = None
        self.pending_clear = False
        self.last_track_key = ""
        self.last_status_text = ""
        self.active: PlayerSnapshot | None = None
        self.last_error = ""
        self.retry_at = 0.0
        self.force_next_send = False
        self._warned_token_for = ""
        self._pending_clear_message = "Discord status cleared."

        self.timer = QTimer(self)
        self.timer.setInterval(POLL_INTERVAL_MS)
        self.timer.timeout.connect(self.refresh)

    # ------------------------------------------------------------------ state
    def start(self) -> None:
        self._log("info", "WhatIsPlaying started.")
        if not self.monitor.available:
            self._log(
                "warning",
                self.monitor.error or "No media session backend is available.",
            )
        self.timer.start()
        self.refresh(force=True)

    def shutdown(self) -> None:
        self.timer.stop()
        stop_monitor = getattr(self.monitor, "stop", None)
        if callable(stop_monitor):
            stop_monitor()
        if (
            (self.discord_has_status or self.pending_send_key)
            and self.config.token.strip()
            and not self.pending_clear
        ):
            self._log("info", "Clearing Discord status before quitting.")
            self.worker.submit_clear(self.config.token)
        self.worker.stop()

    def _save(self) -> None:
        try:
            self.store.save(self.config)
        except OSError as exc:
            self._log("error", f"Could not save settings: {exc}")

    def _log(self, level: str, message: str) -> None:
        getattr(log, level, log.info)(message)
        self.activity.emit(level, message)

    def _emit_state(self, phase: str, message: str) -> None:
        selected = (
            None
            if self.config.selected_players is None
            else tuple(self.config.selected_players)
        )
        self.state_changed.emit(
            AppState(
                enabled=self.config.enabled,
                token_configured=bool(self.config.token.strip()),
                players=self.players,
                selected_players=selected,
                active=self.active,
                phase=phase,
                message=message,
                last_error=self.last_error,
                monitor_error=self._monitor_error,
                status_text=self.last_status_text,
            )
        )

    # --------------------------------------------------------------- settings
    def set_enabled(self, enabled: bool) -> None:
        if self.config.enabled == enabled:
            return
        self.config.enabled = enabled
        self._save()
        self.retry_at = 0.0
        if enabled:
            self._log("info", "Sending to Discord enabled.")
        else:
            self._log("info", "Sending to Discord disabled.")
            self._request_clear("Sending is off — Discord status cleared.")
        self.refresh(force=True)

    def set_token(self, token: str) -> None:
        token = token.strip()
        if token == self.config.token:
            return
        self.config.token = token
        self._save()
        self.last_error = ""
        self.retry_at = 0.0
        self._warned_token_for = ""
        self._log(
            "info",
            "Discord token saved." if token else "Discord token cleared.",
        )
        self.refresh(force=True)

    def set_selected_players(self, selected: set[str] | None) -> None:
        self.config.selected_players = None if selected is None else sorted(selected)
        self._save()
        if selected is None:
            self._log("info", f"Watching all detected {players_name()}.")
        elif not selected:
            self._log("info", "No players are selected.")
        else:
            self._log("info", f"Watching {len(selected)} player(s).")
        self.retry_at = 0.0
        self.refresh(force=True)

    def set_append_kaomoji(self, enabled: bool) -> None:
        if self.config.append_kaomoji == enabled:
            return
        self.config.append_kaomoji = enabled
        self._save()
        self._log("info", "Kaomoji appended to statuses." if enabled else "Kaomoji disabled.")
        self.force_next_send = True
        self.refresh(force=True)

    def set_close_to_tray(self, enabled: bool) -> None:
        self.config.close_to_tray = enabled
        self._save()

    def refresh_players(self) -> None:
        self.refresh(force=True)

    def force_resend(self) -> None:
        self.force_next_send = True
        self.refresh(force=True)

    # ------------------------------------------------------------ Discord ops
    def test_status(self) -> None:
        token = self.config.token.strip()
        if not token:
            self._log("warning", "Add a Discord token before sending a test status.")
            return
        text = "WhatIsPlaying test (｡･ω･｡)"
        self.worker.submit_update(token, text, TEST_KEY)
        self._log("info", "Sending a test status to Discord…")

    def clear_status(self) -> None:
        if self.config.enabled:
            self.config.enabled = False
            self._save()
            self._log("info", "Sending to Discord disabled so the status stays cleared.")
        self._request_clear("Discord status cleared.")

    def _request_clear(self, success_message: str) -> None:
        token = self.config.token.strip()
        if not token:
            if self.status_shown:
                self._log(
                    "warning",
                    "Cannot clear the Discord status without a saved token.",
                )
            return
        if self.pending_clear:
            return
        if not self.discord_has_status and not self.pending_send_key:
            return
        self.pending_clear = True
        self._pending_clear_message = success_message
        self.worker.submit_clear(token)

    # --------------------------------------------------------------- main poll
    def refresh(self, force: bool = False) -> None:
        if force:
            self.retry_at = 0.0

        try:
            players = self.monitor.refresh()
        except Exception as exc:  # noqa: BLE001 - keep the app alive
            log.exception("Media refresh failed")
            players = []
            self._monitor_error = f"Media error: {exc}"
        else:
            self._monitor_error = self.monitor.error

        self.players = tuple(players)
        self._log_player_changes(players)

        eligible = [p for p in players if self.config.is_watched(p.key)]
        playing = [p for p in eligible if p.is_playing and p.title.strip()]
        if playing:
            self.active = playing[0]
        elif eligible:
            previous = self.active
            self.active = next(
                (p for p in eligible if previous and p.key == previous.key),
                eligible[0],
            )
        else:
            self.active = None

        if not self.config.enabled:
            self._emit_state("disabled", "Sending is off. Your Discord status is left alone.")
            return

        if not self.config.token.strip():
            if playing and track_key_for(playing[0]) != self._warned_token_for:
                self._warned_token_for = track_key_for(playing[0])
                self._log("warning", "Discord token is not set; status not sent.")
            self._emit_state(
                "token-missing",
                "Add your Discord token below to start sharing.",
            )
            return

        if playing:
            self._handle_playing(playing[0])
            return

        # Nothing is playing: make sure the previously shared status is gone.
        if self.discord_has_status or self.pending_send_key:
            if time.monotonic() >= self.retry_at:
                self._request_clear("Playback paused — Discord status cleared.")
            else:
                self._emit_state("error", "Discord request failed. Retrying shortly.")
                return

        if not players:
            self._emit_state(
                "no-players",
                f"No {player_name()} detected. Start a music player and press Refresh.",
            )
        elif not eligible:
            self._emit_state(
                "not-watching",
                "None of the selected players is active.",
            )
        else:
            self._emit_state(
                "paused",
                (
                    "Clearing the Discord status…"
                    if self.pending_clear
                    else "Playback paused. The Discord status is cleared."
                ),
            )

    def _handle_playing(self, player: PlayerSnapshot) -> None:
        title = clean_title(player.title) or player.title
        artist = clean_artist(player.artist) or player.artist
        track_key = f"{player.key}\x00{title}\x00{artist}"
        track_changed = track_key != self.last_track_key

        if track_changed:
            self._log("info", f"Now playing: {title} — {artist} ({player.identity})")

        if time.monotonic() < self.retry_at:
            self._emit_state("error", "Discord request failed. Retrying shortly.")
            return

        needs_send = (
            self.force_next_send
            or not self.status_shown
            or self.last_track_key != track_key
        )
        if needs_send and self.pending_send_key != track_key:
            text = build_status(
                title,
                artist,
                append_kaomoji=self.config.append_kaomoji,
            )
            self.pending_send_key = track_key
            self.last_track_key = track_key
            self.last_status_text = text
            self.force_next_send = False
            self.worker.submit_update(self.config.token, text, track_key)
            self._log("info", f"Updating Discord status: {text}")
            self._emit_state("updating", "Sending the new track to Discord…")
            return

        self._emit_state(
            "playing",
            "Your custom status updates automatically while music plays.",
        )

    def _log_player_changes(self, players: list[PlayerSnapshot]) -> None:
        current = {p.key: p.identity for p in players}
        if not self._initial_player_scan:
            self._initial_player_scan = True
            if players:
                self._log(
                    "info",
                    f"Detected {len(players)} {players_name()}: "
                    + ", ".join(p.identity for p in players),
                )
            else:
                self._log("info", f"No {players_name()} detected yet.")
        else:
            for key, identity in current.items():
                if key not in self._known_players:
                    self._log("info", f"Player connected: {identity}")
            for key, identity in self._known_players.items():
                if key not in current:
                    self._log("info", f"Player disconnected: {identity}")
        self._known_players = current

    # ---------------------------------------------------------- worker events
    def _on_updated(self, key: str, text: str) -> None:
        self.discord_has_status = True
        if key == TEST_KEY:
            self._log(
                "info",
                "Test status sent to Discord. It will be replaced on the next update.",
            )
            # Test statuses overwrite the current track. Restore it right away.
            if (
                self.config.enabled
                and self.active is not None
                and self.active.is_playing
            ):
                self.status_shown = False
                self.force_next_send = True
                self.refresh(force=True)
            return

        if self.pending_send_key == key:
            self.pending_send_key = None
        if self.last_track_key == key:
            self.status_shown = True
        self.last_error = ""
        self.retry_at = 0.0
        self._log("info", "Discord custom status updated.")
        self.refresh()

    def _on_cleared(self) -> None:
        self.pending_clear = False
        self.status_shown = False
        self.discord_has_status = False
        self.pending_send_key = None
        self.last_track_key = ""
        self.last_status_text = ""
        self.last_error = ""
        self.retry_at = 0.0
        message = getattr(self, "_pending_clear_message", "Discord status cleared.")
        self._log("info", message)
        self.refresh()

    def _on_failed(
        self,
        action: str,
        key: str,
        message: str,
        retry_after: float,
        status: int,
    ) -> None:
        if action == "clear":
            self.pending_clear = False
        else:
            # A failed update means the previous track may still be on Discord,
            # but we still need to retry the current one after the cooldown.
            self.status_shown = False
            if self.pending_send_key == key:
                self.pending_send_key = None

        self.last_error = message
        if status in (401, 403):
            delay = max(retry_after, 60.0)
        elif status == 429:
            delay = max(retry_after, 10.0)
        else:
            delay = max(retry_after, 15.0)
        self.retry_at = time.monotonic() + delay
        self._log("error", message)
        self._emit_state("error", "Discord request failed. Retrying shortly.")
