"""Start-at-login integration for the current platform.

Linux uses an XDG autostart desktop entry; Windows uses the per-user
``CurrentVersion\\Run`` registry key. Keeping the platform code in separate
modules means the app never imports ``winreg`` on Linux or XDG helpers on
Windows.
"""

from __future__ import annotations

import sys

if sys.platform == "win32":
    from .autostart_windows import (
        autostart_path,
        is_enabled,
        launch_command,
        set_enabled,
    )
else:
    from .autostart_linux import (
        autostart_path,
        is_enabled,
        launch_command,
        set_enabled,
    )

__all__ = ["autostart_path", "is_enabled", "launch_command", "set_enabled"]
