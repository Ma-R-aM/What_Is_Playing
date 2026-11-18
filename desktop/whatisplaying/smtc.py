"""Read media sessions from the Windows System Media Transport Controls API.

Windows 10 (1809+) and Windows 11 expose every well-behaved media player
through ``Windows.Media.Control``. The Python projection lives in the
``winrt-Windows.Media.Control`` package (PyWinRT) and is imported lazily so the
rest of the app, and the test suite, can run on Linux.

WinRT's blocking ``.get()`` must not be called from a single-threaded apartment
(the Qt GUI thread). The monitor therefore polls on a small daemon thread and
hands the controller a cached snapshot through :meth:`refresh`.
"""

from __future__ import annotations

import logging
import re
import sys
import threading
from types import SimpleNamespace

from .media import (
    PAUSED,
    PLAYING,
    STOPPED,
    UNKNOWN,
    PlayerSnapshot,
    dedupe_players,
)

log = logging.getLogger(__name__)

DEFAULT_POLL_SECONDS = 1.5

# Windows reports an Application User Model ID (AUMID). For unpackaged apps it
# is usually just the executable name; packaged apps use a package family name
# followed by an application id, for example
# ``SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify``.
_KNOWN_APPS = {
    "spotify": "Spotify",
    "spotify.exe": "Spotify",
    "spotifyab.spotifymusic_zpdnekdrzrea0!spotify": "Spotify",
    "vlc": "VLC",
    "vlc.exe": "VLC",
    "musicbee": "MusicBee",
    "musicbee.exe": "MusicBee",
    "foobar2000": "foobar2000",
    "foobar2000.exe": "foobar2000",
    "aimp": "AIMP",
    "aimp.exe": "AIMP",
    "tidal": "TIDAL",
    "tidal.exe": "TIDAL",
    "deezer": "Deezer",
    "deezer.exe": "Deezer",
    "amazonmusic.exe": "Amazon Music",
    "applemusic.exe": "Apple Music",
    "itunes.exe": "iTunes",
    "cider.exe": "Cider",
    "wmplayer.exe": "Windows Media Player",
    "microsoft.zunemusic_8wekyb3d8bbwe!microsoft.zunemusic": "Media Player",
    "microsoft.media.player_8wekyb3d8bbwe!microsoft.media.player": "Media Player",
}

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

# Chromium-based browsers extend their AUMID with the profile name and, for
# installed web apps, the app URL, for example ``Chrome.Default`` or
# ``MSEdge.127.0.0.1_example.com.Default``. Collapse those variants so each
# browser shows up once under its friendly name.
_BROWSER_FAMILIES = {
    "chrome": ("chrome", "Google Chrome"),
    "msedge": ("msedge", "Microsoft Edge"),
    "microsoftedge": ("msedge", "Microsoft Edge"),
    "firefox": ("firefox", "Firefox"),
    "brave": ("brave", "Brave"),
    "opera": ("opera", "Opera"),
    "vivaldi": ("vivaldi", "Vivaldi"),
}


def _load_control_module():
    from winrt.windows.media.control import (  # noqa: PLC0415 - optional platform dep
        GlobalSystemMediaTransportControlsSessionManager,
        GlobalSystemMediaTransportControlsSessionPlaybackStatus,
    )

    return SimpleNamespace(
        GlobalSystemMediaTransportControlsSessionManager=(
            GlobalSystemMediaTransportControlsSessionManager
        ),
        GlobalSystemMediaTransportControlsSessionPlaybackStatus=(
            GlobalSystemMediaTransportControlsSessionPlaybackStatus
        ),
    )


_APARTMENT_LOCAL = threading.local()

# COM returns this when the thread already has an apartment with another mode.
_RPC_E_CHANGED_MODE = -2147417850  # 0x80010106


def _co_initialize_ex() -> bool:
    """Fallback COM initialization when PyWinRT's helper is unavailable."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes  # noqa: PLC0415 - Windows-only fallback

        # COINIT_MULTITHREADED: the polling thread blocks on WinRT ``.get()``
        # calls, so it must not live in a single-threaded apartment.
        result = ctypes.windll.ole32.CoInitializeEx(None, 0x0)
    except Exception as exc:  # noqa: BLE001 - optional platform dependency
        log.debug("COM initialization failed: %s", exc)
        return False
    # S_OK (0), S_FALSE (1, already initialized) and RPC_E_CHANGED_MODE all
    # leave the thread with an apartment that WinRT can use.
    return result in (0, 1, _RPC_E_CHANGED_MODE)


def _initialize_com() -> bool:
    try:
        from winrt.runtime import (  # noqa: PLC0415 - optional platform dep
            ApartmentType,
            init_apartment,
        )
    except Exception as exc:  # noqa: BLE001 - fall back to plain COM
        log.debug("winrt.runtime unavailable (%s); initializing COM directly", exc)
        return _co_initialize_ex()

    try:
        init_apartment(ApartmentType.MULTI_THREADED)
    except TypeError:
        # Older PyWinRT releases took no argument and defaulted to MTA.
        try:
            init_apartment()  # type: ignore[call-arg]
        except Exception as exc:  # noqa: BLE001 - fall back to plain COM
            log.debug("WinRT apartment initialization skipped: %s", exc)
            return _co_initialize_ex()
    except Exception as exc:  # noqa: BLE001 - maybe already initialized
        log.debug("WinRT apartment initialization skipped: %s", exc)
        return _co_initialize_ex()
    return True


def _init_apartment() -> None:
    """Initialize WinRT/COM for the calling thread, at most once per thread.

    The polling thread we create must opt in before it touches the
    media-control APIs. Repeated calls on the same thread are a no-op, and the
    marker dies with the thread.
    """
    if getattr(_APARTMENT_LOCAL, "ready", False):
        return
    if _initialize_com():
        _APARTMENT_LOCAL.ready = True


def _humanize_app_id(app_id: str) -> str:
    candidate = app_id.split("!", 1)[-1] if "!" in app_id else app_id
    candidate = candidate.rsplit("\\", 1)[-1]
    candidate = re.sub(r"\.exe$", "", candidate, flags=re.IGNORECASE)
    candidate = _CAMEL_BOUNDARY.sub(" ", candidate)
    candidate = candidate.replace("_", " ").replace("-", " ").strip()
    candidate = " ".join(candidate.split())
    return candidate.title() if candidate else "Media player"


def _browser_family(key: str) -> tuple[str, str] | None:
    """Match browser AUMIDs such as ``chrome.default`` or ``msedge.<app>``."""
    stem = key.removesuffix(".exe").split(".", 1)[0]
    return _BROWSER_FAMILIES.get(stem)


def describe_app(app_id: str) -> tuple[str, str]:
    """Return ``(stable key, friendly name)`` for an SMTC AUMID."""
    raw = (app_id or "").strip()
    if not raw:
        return "unknown", "Media player"
    key = raw.casefold()
    identity = _KNOWN_APPS.get(key) or _KNOWN_APPS.get(key.removesuffix(".exe"))
    if identity is None:
        family = _browser_family(key)
        if family is not None:
            key, identity = family
    return key, identity or _humanize_app_id(raw)


def _status_name(value, status_enum) -> str:
    for attribute, name in (
        ("PLAYING", PLAYING),
        ("PAUSED", PAUSED),
        ("STOPPED", STOPPED),
    ):
        candidate = getattr(status_enum, attribute, None)
        if candidate is not None and value == candidate:
            return name

    # Be forgiving of test doubles and future PyWinRT enum changes.
    raw_name = getattr(value, "name", "")
    if isinstance(raw_name, str):
        raw_name = raw_name.upper()
        if raw_name in {"PLAYING", "PAUSED", "STOPPED", "CLOSED"}:
            return STOPPED if raw_name == "CLOSED" else raw_name.title()
    return UNKNOWN


class WindowsMediaMonitor:
    """Poll SMTC sessions on a background thread and cache the newest result."""

    def __init__(
        self,
        *,
        control=None,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
    ) -> None:
        self._control = control
        self._poll_seconds = max(0.1, float(poll_seconds))
        self._lock = threading.Lock()
        self._start_lock = threading.Lock()
        self._snapshots: list[PlayerSnapshot] = []
        self._error = ""
        self._manager = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._first_scan = threading.Event()

        if self._control is None:
            try:
                self._control = _load_control_module()
            except Exception as exc:  # noqa: BLE001 - show a useful hint instead
                log.debug("Could not import WinRT media controls: %s", exc)
                self._error = (
                    "Windows media controls are unavailable. Install the WinRT "
                    f"packages listed in packaging/windows/requirements-windows.txt ({exc})."
                )

    @property
    def available(self) -> bool:
        return self._control is not None

    @property
    def error(self) -> str:
        with self._lock:
            return self._error

    @property
    def snapshots(self) -> list[PlayerSnapshot]:
        with self._lock:
            return list(self._snapshots)

    # --------------------------------------------------------------- polling
    def refresh(self) -> list[PlayerSnapshot]:
        if not self.available:
            return []
        self._ensure_thread()
        return self.snapshots

    def wait_until_ready(self, timeout: float = 5.0) -> bool:
        """Wait for the first scan; used by the ``--list-players`` CLI."""
        if not self.available:
            return False
        self._ensure_thread()
        return self._first_scan.wait(max(0.0, timeout))

    def poll_once(self) -> list[PlayerSnapshot]:
        """Scan synchronously. The worker thread and tests use this."""
        if self._control is None:
            return []
        _init_apartment()
        if self._manager is None:
            manager_class = self._control.GlobalSystemMediaTransportControlsSessionManager
            self._manager = manager_class.request_async().get()
        snapshots = self._scan(self._manager)
        self._publish(snapshots, "")
        return snapshots

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=max(2.0, self._poll_seconds + 1.5))

    # ---------------------------------------------------------------- worker
    def _ensure_thread(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        with self._start_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="whatisplaying-smtc",
                daemon=True,
            )
            self._thread.start()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.poll_once()
            except Exception as exc:  # noqa: BLE001 - never kill the GUI
                log.warning("Windows media scan failed: %s", exc)
                self._manager = None
                self._publish([], f"Windows media error: {exc}")
            finally:
                self._first_scan.set()
            if self._stop_event.wait(self._poll_seconds):
                return

    def _publish(self, snapshots: list[PlayerSnapshot], error: str) -> None:
        with self._lock:
            self._snapshots = list(snapshots)
            self._error = error

    def _scan(self, manager) -> list[PlayerSnapshot]:
        status_enum = (
            self._control.GlobalSystemMediaTransportControlsSessionPlaybackStatus
        )
        snapshots: list[PlayerSnapshot] = []
        for session in manager.get_sessions():
            try:
                snapshot = self._snapshot(session, status_enum)
            except Exception as exc:  # noqa: BLE001 - one broken session is fine
                log.debug("Skipping Windows media session: %s", exc)
                continue
            if snapshot is not None:
                snapshots.append(snapshot)
        return dedupe_players(snapshots)

    @staticmethod
    def _snapshot(session, status_enum) -> PlayerSnapshot | None:
        app_id = str(getattr(session, "source_app_user_model_id", "") or "").strip()
        key, identity = describe_app(app_id)

        info = session.get_playback_info()
        status = _status_name(getattr(info, "playback_status", None), status_enum)

        title = artist = album = track_id = ""
        operation = session.try_get_media_properties_async()
        if operation is not None:
            properties = operation.get()
            if properties is not None:
                title = str(getattr(properties, "title", "") or "").strip()
                artist = str(getattr(properties, "artist", "") or "").strip()
                album = str(getattr(properties, "album_title", "") or "").strip()
                number = getattr(properties, "track_number", 0)
                if number:
                    track_id = f"track:{number}"

        if not app_id and not title:
            return None
        # Idle sessions with no metadata are noise; paused sessions are kept so
        # the player picker still lists them.
        if not title and status not in (PLAYING, PAUSED):
            return None

        return PlayerSnapshot(
            bus_name=app_id or key,
            key=key,
            identity=identity,
            desktop_entry=app_id,
            playback_status=status,
            title=title,
            artist=artist,
            album=album,
            track_id=track_id,
        )
