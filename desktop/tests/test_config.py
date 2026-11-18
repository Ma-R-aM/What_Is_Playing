from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from whatisplaying.config import Config, ConfigStore, config_home, state_home


class ConfigStoreTest(unittest.TestCase):
    def test_round_trip_and_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "config.json"
            store = ConfigStore(path)
            config = Config(
                enabled=False,
                token="  abc.def  ",
                selected_players=["spotify", "vlc", "spotify"],
                append_kaomoji=False,
                close_to_tray=False,
            )
            store.save(config)
            if os.name != "nt":
                # POSIX mode bits are meaningful; Windows only tracks the
                # read-only flag and relies on the profile directory ACL.
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

            loaded = store.load()
            self.assertFalse(loaded.enabled)
            self.assertEqual(loaded.token, "abc.def")
            self.assertEqual(loaded.selected_players, ["spotify", "vlc"])
            self.assertFalse(loaded.append_kaomoji)
            self.assertFalse(loaded.close_to_tray)

    def test_missing_file_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = ConfigStore(Path(tmp) / "missing.json").load()
            self.assertTrue(config.enabled)
            self.assertIsNone(config.selected_players)
            self.assertEqual(config.token, "")

    def test_malformed_file_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("{not json", encoding="utf-8")
            config = ConfigStore(path).load()
            self.assertTrue(config.enabled)

    def test_unknown_types_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "enabled": "yes",
                        "token": 42,
                        "selected_players": "spotify",
                        "append_kaomoji": None,
                        "close_to_tray": 3,
                    }
                ),
                encoding="utf-8",
            )
            config = ConfigStore(path).load()
            self.assertTrue(config.enabled)
            self.assertEqual(config.token, "")
            self.assertIsNone(config.selected_players)
            self.assertTrue(config.append_kaomoji)
            self.assertTrue(config.close_to_tray)

    def test_selected_players_semantics(self) -> None:
        config = Config(selected_players=None)
        self.assertTrue(config.is_watched("anything"))
        config = Config(selected_players=[])
        self.assertFalse(config.is_watched("anything"))
        config = Config(selected_players=["spotify"])
        self.assertTrue(config.is_watched("spotify"))
        self.assertFalse(config.is_watched("vlc"))

    @unittest.skipUnless(sys.platform == "win32", "Windows path convention")
    def test_windows_appdata_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "APPDATA": str(Path(tmp) / "Roaming"),
                "LOCALAPPDATA": str(Path(tmp) / "Local"),
            }
            with mock.patch.dict(os.environ, env, clear=False):
                self.assertEqual(config_home(), Path(env["APPDATA"]))
                self.assertEqual(state_home(), Path(env["LOCALAPPDATA"]))


if __name__ == "__main__":
    unittest.main()
