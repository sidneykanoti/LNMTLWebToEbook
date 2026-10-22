import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

module_path = Path(__file__).resolve().parents[1] / "scripts" / "publish_release.py"
spec = importlib.util.spec_from_file_location("publish_release", module_path)
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class ReleaseTests(unittest.TestCase):
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
