from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from whatisplaying import autostart

if sys.platform == "win32":
    from whatisplaying import autostart_windows

IS_WINDOWS = sys.platform == "win32"


class LaunchCommandTest(unittest.TestCase):
    def test_launch_command_is_nonempty(self) -> None:
        args, env = autostart.launch_command()
        self.assertTrue(args)
        self.assertEqual(args[-1], "--minimized")
        for key, value in env.items():
            self.assertIsInstance(key, str)
            self.assertIsInstance(value, str)


@unittest.skipIf(IS_WINDOWS, "XDG autostart is only used on Linux")
class LinuxAutostartTest(unittest.TestCase):
    def test_enable_and_disable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = {"XDG_CONFIG_HOME": tmp}
            with mock.patch.dict(os.environ, env, clear=False):
                self.assertFalse(autostart.is_enabled())
                autostart.set_enabled(True)
                self.assertTrue(autostart.is_enabled())
                path = autostart.autostart_path()
                self.assertEqual(path.parent, Path(tmp) / "autostart")
                text = path.read_text(encoding="utf-8")
                self.assertIn("[Desktop Entry]", text)
                self.assertIn("--minimized", text)
                self.assertIn("Exec=", text)

                autostart.set_enabled(False)
                self.assertFalse(autostart.is_enabled())


class _FakeKey:
    def __init__(self, fake: "_FakeWinreg") -> None:
        self.fake = fake

    def __enter__(self) -> "_FakeKey":
        return self

    def __exit__(self, *_exc) -> bool:
        return False


class _FakeWinreg:
    HKEY_CURRENT_USER = object()
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.key_exists = True

    def OpenKey(self, root, path, reserved, access) -> _FakeKey:
        if not self.key_exists:
            raise FileNotFoundError(path)
        del root, path, reserved, access
        return _FakeKey(self)

    def CreateKeyEx(self, root, path, reserved, access) -> _FakeKey:
        del root, path, reserved, access
        self.key_exists = True
        return _FakeKey(self)

    def QueryValueEx(self, key: _FakeKey, name: str):
        try:
            return key.fake.values[name], self.REG_SZ
        except KeyError:
            raise FileNotFoundError(name) from None

    def SetValueEx(
        self, key: _FakeKey, name: str, reserved: int, kind: int, value: str
    ) -> None:
        del reserved, kind
        key.fake.values[name] = value

    def DeleteValue(self, key: _FakeKey, name: str) -> None:
        try:
            del key.fake.values[name]
        except KeyError:
            raise FileNotFoundError(name) from None


@unittest.skipUnless(IS_WINDOWS, "the registry autostart is only used on Windows")
class WindowsAutostartTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(
            os.environ, {"LOCALAPPDATA": self.tmp.name}, clear=False
        )
        env.start()
        self.addCleanup(env.stop)

        self.fake_winreg = _FakeWinreg()
        registry = mock.patch.object(
            autostart_windows, "winreg", self.fake_winreg
        )
        registry.start()
        self.addCleanup(registry.stop)

    def test_enable_and_disable(self) -> None:
        self.assertFalse(autostart.is_enabled())

        autostart.set_enabled(True)
        self.assertTrue(autostart.is_enabled())
        launcher = autostart.autostart_path()
        self.assertEqual(launcher.parent, Path(self.tmp.name) / "WhatIsPlaying")
        self.assertTrue(launcher.is_file())
        text = launcher.read_text(encoding="utf-8")
        self.assertIn("--minimized", text)
        self.assertIn("whatisplaying", text)
        self.assertEqual(
            self.fake_winreg.values[autostart_windows.REGISTRY_KEY],
            f'"{launcher}"',
        )

        autostart.set_enabled(False)
        self.assertFalse(autostart.is_enabled())
        self.assertFalse(launcher.exists())

    def test_missing_run_key_is_disabled(self) -> None:
        self.fake_winreg.key_exists = False
        self.assertFalse(autostart.is_enabled())
        autostart.set_enabled(False)
        self.assertFalse(autostart.is_enabled())


if __name__ == "__main__":
    unittest.main()
