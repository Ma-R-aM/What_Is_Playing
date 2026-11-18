"""XDG autostart integration for Linux."""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

log = logging.getLogger(__name__)

AUTOSTART_NAME = "whatisplaying.desktop"


def autostart_dir() -> Path:
    override = os.environ.get("XDG_CONFIG_HOME")
    base = Path(override) if override else Path.home() / ".config"
    return base / "autostart"


def autostart_path() -> Path:
    return autostart_dir() / AUTOSTART_NAME


def _package_root() -> Path:
    # /usr/lib/whatisplaying/whatisplaying -> /usr/lib/whatisplaying
    return Path(__file__).resolve().parent.parent


def launch_command() -> tuple[list[str], dict[str, str]]:
    """Return the command and extra environment used to start the app."""
    root = _package_root()
    wrapper = root.parent.parent / "bin" / "whatisplaying"
    if wrapper.is_file() and os.access(wrapper, os.X_OK):
        return [str(wrapper), "--minimized"], {}

    found = shutil.which("whatisplaying")
    if found:
        return [found, "--minimized"], {}

    # Running directly from a source checkout.
    return [sys.executable, "-m", "whatisplaying", "--minimized"], {
        "PYTHONPATH": str(root)
    }


def _exec_quote(value: str) -> str:
    """Quote a value for the Exec key of a desktop entry.

    Desktop-entry quoting is not shell quoting; only double quotes are
    special, and only a few characters are escaped inside them.
    """
    if value and all(character.isalnum() or character in "._-/:=,+" for character in value):
        return value
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("`", "\\`")
        .replace("$", "\\$")
    )
    return f'"{escaped}"'


def is_enabled() -> bool:
    return autostart_path().is_file()


def set_enabled(enabled: bool) -> None:
    path = autostart_path()
    if not enabled:
        try:
            path.unlink()
        except FileNotFoundError:
            return
        return

    args, env = launch_command()
    if env:
        env_string = " ".join(
            f"{key}={_exec_quote(value)}" for key, value in env.items()
        )
        command = "env " + env_string + " " + " ".join(_exec_quote(arg) for arg in args)
    else:
        command = " ".join(_exec_quote(arg) for arg in args)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Version=1.0",
                "Name=WhatIsPlaying",
                "Comment=Share what you are listening to as a Discord custom status",
                f"Exec={command}",
                "Icon=whatisplaying",
                "Terminal=false",
                "X-GNOME-Autostart-enabled=true",
                "Categories=AudioVideo;Audio;",
                "",
            ]
        ),
        encoding="utf-8",
    )
    log.info("Enabled autostart: %s", path)
