import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lnmtl import platform_support as support
from lnmtl.library import Library


class PlatformTests(unittest.TestCase):
    def test_platform_storage_paths(self):
        home = Path.cwd() / "example-home"
        self.assertEqual(support.user_data_directory("win32", home, {}), home / "AppData" / "Local" / "LNMTLWebToEbook")
        self.assertEqual(support.user_data_directory("darwin", home, {}), home / "Library" / "Application Support" / "LNMTLWebToEbook")
        self.assertEqual(support.user_data_directory("linux", home, {}), home / ".local" / "share" / "LNMTLWebToEbook")
        custom = Path.cwd() / "custom-data"
        self.assertEqual(support.user_data_directory("linux", home, {"XDG_DATA_HOME": str(custom)}), custom / "LNMTLWebToEbook")
        self.assertEqual(support.user_data_directory("linux", home, {"XDG_DATA_HOME": "relative"}), home / ".local" / "share" / "LNMTLWebToEbook")

    def test_frozen_storage_is_outside_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            location = Path(tmp)
            with patch.dict(os.environ, {}, clear=True), patch.object(sys, "frozen", True, create=True), patch.object(support, "user_data_directory", return_value=location):
                self.assertEqual(support.library_directory(), location / "library")
                self.assertEqual(support.output_directory(), location / "output")

    def test_selected_library_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.dict(os.environ, {}, clear=True), patch.object(support, "user_data_directory", return_value=root / "prefs"):
                target = support.choose_library_directory(root / "old library")
                os.environ.pop("LNMTL_LIBRARY_DIR")
                self.assertEqual(support.library_directory(), target)
                lib = Library()
                self.assertEqual(lib.root, target)
                lib.close()
                self.assertEqual(json.loads((root / "prefs" / "preferences.json").read_text())["library"], str(target))

    def test_corrupt_preferences_fall_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "preferences.json").write_text("broken")
            with patch.dict(os.environ, {}, clear=True), patch.object(support, "user_data_directory", return_value=root), patch.object(sys, "frozen", True, create=True):
                self.assertEqual(support.library_directory(), root / "library")

    def test_packaged_engine_ignores_browser_cache_override(self):
        with patch.dict(os.environ, {"PLAYWRIGHT_BROWSERS_PATH": "missing-browser-cache"}), patch.object(sys, "frozen", True, create=True):
            support.configure_runtime()
            self.assertEqual(os.environ["PLAYWRIGHT_BROWSERS_PATH"], "0")

    def test_folder_opening_on_each_os(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp).resolve()
            for platform, executable in (("darwin", "open"), ("linux", "xdg-open")):
                with patch.object(sys, "platform", platform), patch.object(support.subprocess, "Popen") as run:
                    support.open_folder(path)
                    self.assertEqual(run.call_args.args[0], [executable, str(path)])
            with patch.object(sys, "platform", "win32"), patch.object(os, "startfile", create=True) as start:
                support.open_folder(path)
                start.assert_called_once_with(str(path))


if __name__ == "__main__":
    unittest.main()
