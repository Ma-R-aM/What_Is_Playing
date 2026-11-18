"""Platform-neutral media-session model and backend selection.

Linux reads MPRIS over D-Bus and Windows reads the System Media Transport
Controls (SMTC) API. Everything above this module -- the controller, parser,
Discord client and window -- works with the :class:`PlayerSnapshot` values
defined here and does not care which backend produced them.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Protocol

PLAYING = "Playing"
PAUSED = "Paused"
STOPPED = "Stopped"
UNKNOWN = "Unknown"


@dataclass(frozen=True)
class PlayerSnapshot:
    """One media player and its current track, in a backend-neutral shape."""

    bus_name: str
    key: str
    identity: str
    desktop_entry: str
    playback_status: str
    title: str
    artist: str
    album: str
    track_id: str

    @property
    def is_playing(self) -> bool:
        return self.playback_status == PLAYING

    @property
    def display_status(self) -> str:
        return {
            PLAYING: "Playing",
            PAUSED: "Paused",
            STOPPED: "Stopped",
        }.get(self.playback_status, self.playback_status or UNKNOWN)


class MediaMonitor(Protocol):
    """The small surface the controller needs from a platform backend."""

    error: str

    @property
    def available(self) -> bool:
        ...

    def refresh(self) -> list[PlayerSnapshot]:
        ...


def is_windows() -> bool:
    return sys.platform == "win32"


def platform_badge() -> str:
    return "Windows · Media" if is_windows() else "Linux · MPRIS"


def player_name() -> str:
    return "Windows media session" if is_windows() else "MPRIS player"


def players_name() -> str:
    return "Windows media sessions" if is_windows() else "MPRIS players"


def support_hint() -> str:
    if is_windows():
        return "Start a music player that reports to Windows media controls."
    return "Start a music player that supports MPRIS."


def empty_list_hint() -> str:
    if is_windows():
        return (
            "No media sessions detected. Start Spotify, VLC, a browser, or "
            "another media player, then press Refresh."
        )
    return (
        "No MPRIS players detected. Start Spotify, VLC, Firefox, or another "
        "media player, then press Refresh."
    )


def rank_snapshot(snapshot: PlayerSnapshot) -> tuple[int, int]:
    """Prefer playing sessions, then sessions that have a title."""
    status_rank = {PLAYING: 2, PAUSED: 1}.get(snapshot.playback_status, 0)
    has_track = 1 if snapshot.title else 0
    return status_rank, has_track


def dedupe_players(snapshots: list[PlayerSnapshot]) -> list[PlayerSnapshot]:
    """Keep one row per player key, preferring the session that is playing."""
    best: dict[str, PlayerSnapshot] = {}
    for snapshot in snapshots:
        current = best.get(snapshot.key)
        if current is None or rank_snapshot(snapshot) > rank_snapshot(current):
            best[snapshot.key] = snapshot
    return sorted(
        best.values(),
        key=lambda item: (not item.is_playing, item.identity.casefold()),
    )


def create_monitor() -> MediaMonitor:
    """Create the monitor for the current operating system."""
    if is_windows():
        from .smtc import WindowsMediaMonitor

        return WindowsMediaMonitor()

    from .mpris import MprisMonitor

    return MprisMonitor()
