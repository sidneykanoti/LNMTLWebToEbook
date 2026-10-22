import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lnmtl.cleanup import clear_planned_data, plan_cleanup, remove_app_data_folder
from lnmtl.library import Library


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.library = self.root / "library"
        lib = Library(self.library)
        c = {"url": "https://lnmtl.com/chapter/example", "number": 1, "volume": 1, "position": 1, "ordinal": 1, "title": "Example", "volume_title": ""}
        lib.save_index({"slug": "example", "title": "Example", "url": "https://lnmtl.com/novel/example", "chapters": [c]})
        self.raw = self.library / "raw" / "example" / "page.html"
        self.raw.parent.mkdir(parents=True)
        self.raw.write_text("downloaded chapter")
        with lib.db:
            lib.db.execute("UPDATE chapters SET raw_path=?", ("raw/example/page.html",))
        lib.close()
        self.book = self.root / "output" / "example" / "example.epub"
        self.book.parent.mkdir(parents=True)
        self.book.write_text("export")
        (self.book.parent / "archive-report.json").write_text(json.dumps({"source": "https://lnmtl.com/novel/example"}))
        self.unrelated = self.library / "personal-notes.txt"
        self.unrelated.write_text("keep")
        self.extra = self.book.parent / "my-other-book.epub"
        self.extra.write_text("keep")
        self.prefs = self.root / "settings"
        self.prefs.mkdir()
        (self.prefs / "preferences.json").write_text("{}")

    def tearDown(self):
        self.temp.cleanup()

    def test_plan_has_no_side_effects_and_default_keeps_books(self):
        plan = plan_cleanup(root=self.library)
        self.assertTrue(self.raw.exists())
        clear_planned_data(plan)
        self.assertFalse(self.raw.exists())
        self.assertFalse((self.library / "archive.sqlite3").exists())
        self.assertTrue(self.book.exists())
        self.assertTrue(self.unrelated.exists())
        self.assertTrue((self.prefs / "preferences.json").exists())

    def test_optional_books_and_preferences_preserve_unrelated_files(self):
        with patch("lnmtl.cleanup.user_data_directory", return_value=self.prefs):
            clear_planned_data(plan_cleanup(True, True, self.library))
        self.assertFalse(self.book.exists())
        self.assertFalse((self.prefs / "preferences.json").exists())
        self.assertTrue(self.unrelated.exists())
        self.assertTrue(self.extra.exists())

    def test_can_remove_exports_after_cache_was_previously_cleared(self):
        clear_planned_data(plan_cleanup(root=self.library))
        clear_planned_data(plan_cleanup(True, root=self.library))
        self.assertFalse(self.book.exists())
        self.assertTrue(self.extra.exists())

    def test_rejects_path_escape_before_deletion(self):
        lib = Library(self.library)
        with lib.db:
            lib.db.execute("UPDATE chapters SET raw_path='../outside.html'")
        lib.close()
        outside = self.root / "outside.html"
        outside.write_text("must stay")
        with self.assertRaises(ValueError):
            plan_cleanup(root=self.library)
        self.assertTrue(outside.exists())
        self.assertTrue((self.library / "archive.sqlite3").exists())

    def test_cleanup_then_reopen_empty_library(self):
        clear_planned_data(plan_cleanup(root=self.library))
        lib = Library(self.library)
        self.assertEqual(lib.novels(), [])
        self.assertEqual(lib.catalogue(), [])
        lib.close()

    def test_complete_folder_removal_keeps_external_data(self):
        app_data = self.root / "LNMTLWebToEbook"
        (app_data / "library").mkdir(parents=True)
        (app_data / "library" / "archive.sqlite3").write_text("test")
        (app_data / "preferences.json").write_text("{}")
        with patch("lnmtl.cleanup.user_data_directory", return_value=app_data):
            remove_app_data_folder()
        self.assertFalse(app_data.exists())
        self.assertTrue(self.unrelated.exists())
        self.assertTrue(self.book.exists())

    def test_complete_removal_rejects_other_folder(self):
        with patch("lnmtl.cleanup.user_data_directory", return_value=self.library):
            with self.assertRaises(ValueError):
                remove_app_data_folder()
        self.assertTrue(self.library.exists())


if __name__ == "__main__":
    unittest.main()
