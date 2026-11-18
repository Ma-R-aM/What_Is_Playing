"""Windows start-at-login integration using the per-user Run registry key.

The registry value points at a small ``.cmd`` launcher written under
``%LOCALAPPDATA%``. The launcher carries the ``PYTHONPATH`` needed when the app
is started from a source checkout; registry values cannot set environment
variables themselves.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import winreg
from pathlib import Path

log = logging.getLogger(__name__)

REGISTRY_KEY = "WhatIsPlaying"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _local_app_data() -> Path:
    override = os.environ.get("LOCALAPPDATA")
    if override:
        return Path(override)
    return Path.home() / "AppData" / "Local"


def autostart_path() -> Path:
    """The launcher script referenced by the registry entry."""
    return _local_app_data() / "WhatIsPlaying" / "autostart.cmd"


def _pythonw() -> Path:
    """Use pythonw.exe so autostart never opens a console window."""
    executable = Path(sys.executable)
    windowless = executable.with_name("pythonw.exe")
    return windowless if windowless.is_file() else executable


def launch_command() -> tuple[list[str], dict[str, str]]:
    """Return the command and extra environment used to start the app."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--minimized"], {}

    # The package directory is ``.../desktop`` in a checkout and
    # ``.../site-packages`` for an installed copy. Adding either to
    # PYTHONPATH is harmless and keeps source runs working from the registry.
    package_parent = Path(__file__).resolve().parent.parent
    return [str(_pythonw()), "-m", "whatisplaying", "--minimized"], {
        "PYTHONPATH": str(package_parent)
    }


def _write_launcher() -> Path:
    args, env = launch_command()
    path = autostart_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["@echo off", "setlocal"]
    lines.extend(f'set "{key}={value}"' for key, value in env.items())
    lines.append("start \"\" " + subprocess.list2cmdline(args))
    lines.append("endlocal")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def is_enabled() -> bool:
    """Return ``True`` when the app has a Run registry entry."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _kind = winreg.QueryValueEx(key, REGISTRY_KEY)
    except FileNotFoundError:
        return False
    except OSError as exc:
        log.warning("Could not read the autostart registry key: %s", exc)
        return False
    return bool(value)


def set_enabled(enabled: bool) -> None:
    """Create or delete the per-user autostart entry."""
    if not enabled:
        _remove_registry_value()
        try:
            autostart_path().unlink()
        except FileNotFoundError:
            pass
        log.info("Removed autostart registry entry %s", REGISTRY_KEY)
        return

    launcher = _write_launcher()
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, REGISTRY_KEY, 0, winreg.REG_SZ, f'"{launcher}"')
    except OSError:
        try:
            launcher.unlink()
        except OSError:
            pass
        raise
    log.info("Added autostart registry entry %s: %s", REGISTRY_KEY, launcher)


def _remove_registry_value() -> None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, REGISTRY_KEY)
    except FileNotFoundError:
        return
    except OSError as exc:
        log.warning("Could not remove the autostart registry entry: %s", exc)
        raise
