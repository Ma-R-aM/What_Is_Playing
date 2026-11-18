"""Read currently playing media from MPRIS players over D-Bus."""

from __future__ import annotations

import logging
import re

from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusObjectPath

from .media import PlayerSnapshot, dedupe_players

__all__ = ["MprisMonitor", "PlayerSnapshot"]

log = logging.getLogger(__name__)

MPRIS_PREFIX = "org.mpris.MediaPlayer2."
MPRIS_PATH = "/org/mpris/MediaPlayer2"
ROOT_IFACE = "org.mpris.MediaPlayer2"
PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"

_INSTANCE_SUFFIX = re.compile(r"\.instance\d+$", re.IGNORECASE)


def _as_text(value) -> str:
    """Normalize the different value types MPRIS can return."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        parts = (_as_text(item) for item in value)
        return ", ".join(part for part in parts if part)
    # QDBusVariant and a few other Qt wrappers expose asVariant().
    as_variant = getattr(value, "asVariant", None)
    if callable(as_variant):
        with_value = as_variant()
        if with_value is not value:
            return _as_text(with_value)
    return str(value).strip()


class _MprisPlayer:
    def __init__(self, bus_name: str, bus: QDBusConnection) -> None:
        self.bus_name = bus_name
        self.bus = bus
        self.root = QDBusInterface(bus_name, MPRIS_PATH, ROOT_IFACE, bus)
        self.player = QDBusInterface(bus_name, MPRIS_PATH, PLAYER_IFACE, bus)
        for interface in (self.root, self.player):
            # Do not let a broken player freeze the GUI for the D-Bus default
            # 25 second timeout.
            set_timeout = getattr(interface, "setTimeout", None)
            if callable(set_timeout):
                set_timeout(1000)
        if not self.root.isValid() or not self.player.isValid():
            raise RuntimeError(
                f"MPRIS interfaces unavailable: "
                f"{self.root.lastError().message() or self.player.lastError().message()}"
            )

        suffix = bus_name[len(MPRIS_PREFIX) :]
        suffix = _INSTANCE_SUFFIX.sub("", suffix)
        fallback_identity = suffix.replace(".", " ").replace("_", " ").strip().title()
        self.identity = _as_text(self.root.property("Identity")) or fallback_identity
        self.desktop_entry = _as_text(self.root.property("DesktopEntry"))
        self.key = self.desktop_entry or suffix.lower() or bus_name
        self._title = ""
        self._artist = ""
        self._album = ""
        self._track_id = ""
        self._playback_status = ""

    def refresh(self) -> PlayerSnapshot | None:
        status = self.player.property("PlaybackStatus")
        if not self.player.isValid():
            return None
        self._playback_status = _as_text(status)

        metadata = self.player.property("Metadata")
        if not self.player.isValid():
            return None
        if not isinstance(metadata, dict):
            metadata = {}

        title = _as_text(metadata.get("xesam:title"))
        artist = _as_text(metadata.get("xesam:artist"))
        if not artist:
            artist = _as_text(metadata.get("xesam:albumArtist"))
        album = _as_text(metadata.get("xesam:album"))
        raw_track_id = metadata.get("mpris:trackid")
        if isinstance(raw_track_id, QDBusObjectPath):
            track_id = raw_track_id.path()
        else:
            track_id = _as_text(raw_track_id)

        self._title = title
        self._artist = artist
        self._album = album
        self._track_id = track_id

        return PlayerSnapshot(
            bus_name=self.bus_name,
            key=self.key,
            identity=self.identity,
            desktop_entry=self.desktop_entry,
            playback_status=self._playback_status,
            title=self._title,
            artist=self._artist,
            album=self._album,
            track_id=self._track_id,
        )


class MprisMonitor:
    """Poll MPRIS players.

    Polling keeps the implementation small and reliable across players which
    do not emit every property change. Two seconds is cheap over the session
    bus and matches the Android app's lightweight watcher.
    """

    def __init__(self, connection: QDBusConnection | None = None) -> None:
        self._connection = connection or QDBusConnection.sessionBus()
        self._players: dict[str, _MprisPlayer] = {}
        self.error = (
            "" if self._connection.isConnected() else "No D-Bus session bus is available."
        )

    @property
    def available(self) -> bool:
        return self._connection.isConnected()

    def _service_names(self) -> list[str]:
        if not self.available:
            self.error = "No D-Bus session bus is available."
            return []
        reply = self._connection.interface().registeredServiceNames()
        if hasattr(reply, "value"):
            names = reply.value() if reply.isValid() else []
        else:
            names = reply
        self.error = ""
        return [
            str(name)
            for name in names
            if str(name).startswith(MPRIS_PREFIX) and len(str(name)) > len(MPRIS_PREFIX)
        ]

    def refresh(self) -> list[PlayerSnapshot]:
        if not self.available:
            self.error = "No D-Bus session bus is available."
            self._players.clear()
            return []

        names = set(self._service_names())

        # Drop players that have disappeared.
        for bus_name in list(self._players):
            if bus_name not in names:
                del self._players[bus_name]

        snapshots: dict[str, PlayerSnapshot] = {}
        for bus_name in sorted(names):
            player = self._players.get(bus_name)
            if player is None:
                try:
                    player = _MprisPlayer(bus_name, self._connection)
                except Exception as exc:  # noqa: BLE001 - one bad player must not win
                    log.debug("Skipping MPRIS player %s: %s", bus_name, exc)
                    continue
                self._players[bus_name] = player

            try:
                snapshot = player.refresh()
            except Exception as exc:  # noqa: BLE001
                log.debug("Dropping unresponsive MPRIS player %s: %s", bus_name, exc)
                self._players.pop(bus_name, None)
                continue

            if snapshot is None:
                self._players.pop(bus_name, None)
                continue

            # Some applications register more than one MPRIS bus name (for
            # example Firefox instances). Show one row per app and prefer the
            # instance which is actually playing.
            snapshots[snapshot.key] = snapshot

        return dedupe_players(list(snapshots.values()))
