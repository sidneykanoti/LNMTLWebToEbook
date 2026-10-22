"""Publish verified native assets from the tag-triggered GitHub Actions job."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lnmtl.platform_support import APP_NAME, VERSION


def verify_assets(directory):
    root = Path(directory)
    bases = [f"LNMTLWebToEbook-{VERSION}-{target}" for target in
             ("windows-x64", "macos-arm64", "macos-x64", "linux-x64")]
    expected = [bases[0] + ".exe", bases[1] + ".dmg", bases[2] + ".dmg", bases[3] + ".tar.gz", bases[3] + ".deb"]
    for name in expected:
        if not (root / name).is_file():
            raise ValueError(f"Missing platform download: {name}")
    for base in bases:
        report = json.loads((root / f"{base}-self-test.json").read_text(encoding="utf-8"))
        if report.get("passed") is not True or report.get("version") != VERSION:
            raise ValueError(f"Platform acceptance test did not pass: {base}")
        for line in (root / f"{base}-SHA256SUMS.txt").read_text().splitlines():
            expected_hash, filename = line.split(None, 1)
            filename = filename.strip()
            if Path(filename).name != filename:
                raise ValueError("Checksum filename must be a plain filename")
            with (root / filename).open("rb") as stream:
                actual_hash = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual_hash != expected_hash:
                raise ValueError(f"Checksum mismatch: {filename}")
    source = root / f"LNMTLWebToEbook-{VERSION}-source.zip"
    if not source.is_file():
        raise ValueError("Source package missing")
    return sorted(p for p in root.iterdir() if p.is_file())


def main():
    tag = os.environ.get("GITHUB_REF_NAME")
    repository = os.environ.get("GITHUB_REPOSITORY")
    if tag != "v" + VERSION or not repository:
        raise ValueError("Publish only from the matching GitHub version tag")
    assets = verify_assets(ROOT / "release")
    existing = subprocess.run(["gh", "release", "view", tag, "--repo", repository], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if existing.returncode == 0:
        # Reruns replace only assets for this same version tag.
        command = ["gh", "release", "upload", tag, "--repo", repository, "--clobber"]
    else:
        command = ["gh", "release", "create", tag, "--repo", repository, "--verify-tag", "--title", f"{APP_NAME} {VERSION}", "--notes-file", str(ROOT / ".github" / "RELEASE_NOTES.md")]
    subprocess.run([*command, *map(str, assets)], check=True)


if __name__ == "__main__":
    main()
