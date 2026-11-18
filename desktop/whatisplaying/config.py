"""Persistent configuration for the desktop app."""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

CONFIG_VERSION = 1
DEFAULT_WATCH_ALL = None
IS_WINDOWS = sys.platform == "win32"


def _appdata_home(variable: str, fallback: str) -> Path:
    override = os.environ.get(variable)
    if override:
        return Path(override)
    return Path.home() / fallback


def config_home() -> Path:
    if IS_WINDOWS:
        return _appdata_home("APPDATA", "AppData/Roaming")
    override = os.environ.get("XDG_CONFIG_HOME")
    return Path(override) if override else Path.home() / ".config"


def state_home() -> Path:
    if IS_WINDOWS:
        return _appdata_home("LOCALAPPDATA", "AppData/Local")
    override = os.environ.get("XDG_STATE_HOME")
    return Path(override) if override else Path.home() / ".local" / "state"


def default_config_path() -> Path:
    return config_home() / "whatisplaying" / "config.json"


@dataclass
class Config:
    version: int = CONFIG_VERSION
    enabled: bool = True
    token: str = ""
    # ``None`` means "watch every detected media player". An empty list means
    # the user explicitly unchecked everything.
    selected_players: list[str] | None = None
    append_kaomoji: bool = True
    close_to_tray: bool = True
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.token = self.token.strip()
        if self.selected_players is not None:
            self.selected_players = sorted(
                {str(item) for item in self.selected_players if str(item).strip()}
            )

    def is_watched(self, key: str) -> bool:
        return self.selected_players is None or key in self.selected_players


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else default_config_path()

    def load(self) -> Config:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return Config()
        except (OSError, ValueError) as exc:
            log.warning("Could not read %s: %s", self.path, exc)
            return Config()

        if not isinstance(raw, dict):
            log.warning("Ignoring malformed config at %s", self.path)
            return Config()

        selected = raw.get("selected_players", DEFAULT_WATCH_ALL)
        if selected is not None:
            if isinstance(selected, list):
                selected = [str(item) for item in selected]
            else:
                selected = None

        enabled = raw.get("enabled", True)
        append_kaomoji = raw.get("append_kaomoji", True)
        close_to_tray = raw.get("close_to_tray", True)
        token = raw.get("token", "")

        return Config(
            enabled=enabled if isinstance(enabled, bool) else True,
            token=token if isinstance(token, str) else "",
            selected_players=selected,
            append_kaomoji=(
                append_kaomoji if isinstance(append_kaomoji, bool) else True
            ),
            close_to_tray=(
                close_to_tray if isinstance(close_to_tray, bool) else True
            ),
        )

    def save(self, config: Config) -> None:
        payload = asdict(config)
        payload.pop("extra", None)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        fd, tmp_name = tempfile.mkstemp(
            prefix=".config-", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            if hasattr(os, "fchmod"):
                # POSIX: make the file private before writing the token. On
                # Windows the profile directory ACL already limits access.
                os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(tmp_name, self.path)
            if hasattr(os, "chmod"):
                os.chmod(self.path, 0o600)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise
