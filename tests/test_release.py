import hashlib
import importlib.util
import json
import tempfile
import unittest
import os
import subprocess
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path

module_path = Path(__file__).resolve().parents[1] / "scripts" / "publish_release.py"
spec = importlib.util.spec_from_file_location("publish_release", module_path)
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class ReleaseTests(unittest.TestCase):
    def run_publisher(self, root, *, upload_error=False, extra_remote=False):
        release = root / "release"
        release.mkdir()
        self.prepare(release)
        remote = [{"name": p.name, "size": p.stat().st_size} for p in release.iterdir()]
        if extra_remote:
            remote.append({"name": "duplicate-windows-x64.exe", "size": 1})
        results = [SimpleNamespace(returncode=1), SimpleNamespace(returncode=0),
                   subprocess.CalledProcessError(1, "upload") if upload_error else SimpleNamespace(returncode=0),
                   SimpleNamespace(stdout=json.dumps({"assets": remote})), SimpleNamespace(returncode=0)]
        with patch.object(publisher, "ROOT", root), patch.dict(os.environ, {"GITHUB_REF_NAME": "v" + publisher.VERSION,
                          "GITHUB_REPOSITORY": publisher.REPOSITORY}), patch.object(publisher.subprocess, "run", side_effect=results) as run:
            if upload_error:
                with self.assertRaises(subprocess.CalledProcessError):
                    publisher.main()
            elif extra_remote:
                with self.assertRaisesRegex(ValueError, "Unexpected application"):
                    publisher.main()
            else:
                publisher.main()
            return [call.args[0] for call in run.call_args_list]

    def test_uploads_and_checks_draft_before_publishing_stable_latest(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = self.run_publisher(Path(tmp))
            self.assertIn("--draft", calls[1])
            self.assertEqual(calls[2][1:3], ["release", "upload"])
            self.assertEqual(calls[3][1:3], ["release", "view"])
            self.assertEqual(calls[-1][1:3], ["release", "edit"])
            for flag in ("--draft=false", "--prerelease=false", "--latest"):
                self.assertIn(flag, calls[-1])

    def test_failed_upload_or_remote_extra_asset_does_not_publish(self):
        for failure in ("upload_error", "extra_remote"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                calls = self.run_publisher(Path(tmp), **{failure: True})
                self.assertFalse(any(call[1:3] == ["release", "edit"] for call in calls))

    def prepare(self, root):
        for target, suffixes in (("windows-x64", [".exe"]), ("macos-arm64", [".dmg"]), ("macos-x64", [".dmg"]), ("linux-x64", [".tar.gz", ".deb"])):
            base = f"LNMTLWebToEbook-{publisher.VERSION}-{target}"
            checksums = []
            for suffix in suffixes:
                name = base + suffix
                content = ("test download " + name).encode()
                (root / name).write_bytes(content)
                checksums.append(hashlib.sha256(content).hexdigest() + "  " + name)
            (root / (base + "-SHA256SUMS.txt")).write_text("\n".join(checksums))
            (root / (base + "-self-test.json")).write_text(json.dumps({"version": publisher.VERSION, "passed": True}))
        (root / f"LNMTLWebToEbook-{publisher.VERSION}-source.zip").write_bytes(b"test source")

    def test_accepts_all_platforms_with_valid_reports_and_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare(root)
            self.assertTrue(publisher.verify_assets(root))

    def test_missing_platform_blocks_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare(root)
            (root / f"LNMTLWebToEbook-{publisher.VERSION}-macos-arm64.dmg").unlink()
            with self.assertRaisesRegex(ValueError, "Missing platform"):
                publisher.verify_assets(root)

    def test_extra_application_blocks_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare(root)
            (root / "old-windows-x64.exe").write_bytes(b"duplicate")
            with self.assertRaisesRegex(ValueError, "Unexpected application"):
                publisher.verify_assets(root)

    def test_incomplete_checksum_inventory_blocks_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare(root)
            (root / f"LNMTLWebToEbook-{publisher.VERSION}-linux-x64-SHA256SUMS.txt").write_text("")
            with self.assertRaisesRegex(ValueError, "Checksum inventory"):
                publisher.verify_assets(root)

    def test_modified_asset_blocks_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare(root)
            (root / f"LNMTLWebToEbook-{publisher.VERSION}-windows-x64.exe").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
                publisher.verify_assets(root)

    def test_failed_packaged_test_blocks_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare(root)
            (root / f"LNMTLWebToEbook-{publisher.VERSION}-linux-x64-self-test.json").write_text(json.dumps({"version": publisher.VERSION, "passed": False}))
            with self.assertRaisesRegex(ValueError, "acceptance test"):
                publisher.verify_assets(root)


if __name__ == "__main__":
    unittest.main()
