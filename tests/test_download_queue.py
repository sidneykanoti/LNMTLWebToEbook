import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from lnmtl.download_queue import DownloadQueue, runner_lock
from lnmtl.library import Library
from lnmtl.source import AccessBlocked, Stopped


class FakeClient:
    def __init__(self):
        self.stop = threading.Event()
        self.fetches = []
        self.discoveries = []

    def check(self):
        if self.stop.is_set():
            raise Stopped("Paused")

    def discover(self, url, report):
        slug = url.rsplit("/", 1)[-1]
        self.discoveries.append(slug)
        return {"slug": slug, "url": url, "title": slug, "author": "Test", "volumes": [],
                "chapters": [{"url": f"https://lnmtl.com/chapter/{slug}-{number}", "title": "Test",
                              "number": number, "part": None, "volume": 1, "volume_title": "",
                              "ordinal": number, "position": number} for number in (1, 2)]}

    def get(self, url):
        self.fetches.append(url)
        result = Mock()
        result.text = '<div class="chapter-body"><sentence class="translated">A sufficiently long synthetic chapter for the offline archive tests.</sentence></div>'
        return result


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.lib = Library(self.root)
        self.queue = DownloadQueue(self.lib)
        self.novels = [{"url": "https://lnmtl.com/novel/" + slug, "title": slug} for slug in ("one", "two")]

    def tearDown(self):
        self.lib.close()
        self.temp.cleanup()

    def test_queue_survives_restart_and_exports_each_novel_once(self):
        self.queue.enqueue(self.novels, ["epub", "html"])
        self.lib.close()
        self.lib = Library(self.root)
        self.queue = DownloadQueue(self.lib)
        exporter = Mock()
        client = FakeClient()
        updates = []
        current = []
        result = self.queue.run(client, progress=updates.append, exporter=exporter, current=current.append)
        self.assertEqual(result["completed"], 2)
        self.assertEqual(result["saved"], 4)
        self.assertEqual(exporter.call_count, 2)
        self.assertEqual(exporter.call_args.args[2], ["epub", "html"])
        for slug in ("one", "two"):
            chapter_updates = [value for value in current if value["slug"] == slug and value["phase"] == "downloading"]
            self.assertEqual([value["saved"] for value in chapter_updates], [0, 1, 2])
            self.assertTrue(all(value["total"] == 2 for value in chapter_updates))
        self.assertIn("indexing", [value["phase"] for value in current])
        self.assertIn("exporting", [value["phase"] for value in current])
        self.assertEqual(current[-1]["phase"], "completed")
        self.queue.run(client, exporter=exporter)
        self.assertEqual(exporter.call_count, 2)
        self.assertEqual(len(client.fetches), 4)

    def test_pause_resume_skips_saved_chapters(self):
        self.queue.enqueue(self.novels)
        client = FakeClient()
        original = client.get
        def pause_after_one(url):
            result = original(url)
            client.stop.set()
            return result
        client.get = pause_after_one
        with self.assertRaises(Stopped):
            self.queue.run(client)
        self.assertEqual(self.lib.summary("one")["saved"], 1)
        self.assertEqual(self.queue.items()[0]["attempts"], 0)
        resumed = FakeClient()
        current = []
        result = self.queue.run(resumed, current=current.append)
        self.assertEqual(result["completed"], 2)
        first_novel_progress = [value for value in current if value["slug"] == "one" and value["phase"] == "downloading"]
        self.assertEqual(first_novel_progress[0]["saved"], 1)
        self.assertEqual(len(resumed.fetches), 3)
        self.assertNotIn("https://lnmtl.com/chapter/one-1", resumed.fetches)

    def test_failed_index_retries_without_stopping_other_novels(self):
        self.queue.enqueue(self.novels)
        client = FakeClient()
        discover = client.discover
        order = []
        def flaky(url, report):
            order.append(url.rsplit("/", 1)[-1])
            if len(order) == 1:
                raise OSError("Temporary network failure")
            return discover(url, report)
        client.discover = flaky
        # Advance the wall clock between iterations without real retry delays.
        with patch("lnmtl.download_queue.time.time", side_effect=range(0, 10000, 100)):
            result = self.queue.run(client)
        self.assertEqual(order, ["one", "two", "one"])
        self.assertEqual(result["completed"], 2)

    def test_retry_limit_persists_errors_and_manual_resume_recovers(self):
        self.queue.enqueue(self.novels, ["epub"])
        client = FakeClient()
        exporter = Mock(side_effect=OSError("Disk unavailable"))
        with patch("lnmtl.download_queue.time.time", side_effect=range(0, 10000, 100)):
            result = self.queue.run(client, exporter=exporter)
        self.assertEqual(result["failed"], 2)
        self.assertTrue(all(row["attempts"] == 3 and "Disk unavailable" in row["error"] for row in self.queue.items()))
        self.assertEqual(len(client.fetches), 4)
        self.assertEqual(self.queue.run(client, exporter=Mock())["completed"], 2)
        self.assertEqual(len(client.fetches), 4)

    def test_failed_chapter_retries_without_downloading_successful_chapters_again(self):
        self.queue.enqueue(self.novels)
        client = FakeClient()
        original = client.get
        calls = []
        def flaky(url):
            calls.append(url)
            if url.endswith("one-1") and calls.count(url) == 1:
                raise OSError("Temporary chapter failure")
            return original(url)
        client.get = flaky
        with patch("lnmtl.download_queue.time.time", side_effect=range(0, 10000, 100)):
            result = self.queue.run(client)
        self.assertEqual(result["completed"], 2)
        self.assertEqual(calls.count("https://lnmtl.com/chapter/one-1"), 2)
        self.assertEqual(calls.count("https://lnmtl.com/chapter/one-2"), 1)

    def test_access_block_stops_queue_without_marking_other_jobs_failed(self):
        self.queue.enqueue(self.novels)
        client = FakeClient()
        client.discover = Mock(side_effect=AccessBlocked("Blocked"))
        with self.assertRaises(AccessBlocked):
            self.queue.run(client)
        self.assertTrue(all(row["state"] == "pending" for row in self.queue.items()))
        self.assertEqual(client.discover.call_count, 1)

    def test_recovers_running_row_after_abrupt_exit(self):
        self.queue.enqueue(self.novels)
        self.queue._update(self.novels[0]["url"], state="running", attempts=1)
        self.assertEqual(self.queue.run(FakeClient())["completed"], 2)
        self.assertEqual(self.queue.items()[0]["attempts"], 1)

    def test_single_runner_and_duplicate_queue_entries(self):
        self.queue.enqueue(self.novels + self.novels)
        self.assertEqual(len(self.queue.items()), 2)
        with runner_lock(self.root):
            with self.assertRaisesRegex(RuntimeError, "already running"):
                self.queue.run(FakeClient())


if __name__ == "__main__":
    unittest.main()
