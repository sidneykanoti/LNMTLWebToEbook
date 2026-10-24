"""Publish verified native assets from the tag-triggered GitHub Actions job."""
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lnmtl.platform_support import APP_NAME, VERSION


REPOSITORY = "sidneykanoti/LNMTLWebToEbook"
SUFFIXES = ("windows-x64.exe", "macos-arm64.dmg", "macos-x64.dmg",
            "linux-x64.tar.gz", "linux-x64.deb")


def verify_names(names):
    expected = {f"LNMTLWebToEbook-{VERSION}-{suffix}" for suffix in SUFFIXES}
    applications = {name for name in names if name.endswith((".exe", ".dmg", ".tar.gz", ".deb"))}
    missing = expected - applications
    if missing:
        raise ValueError("Missing platform download: " + ", ".join(sorted(missing)))
    if applications != expected:
        raise ValueError("Unexpected application downloads: " + ", ".join(sorted(applications - expected)))


def verify_assets(directory):
    root = Path(directory)
    verify_names(p.name for p in root.iterdir() if p.is_file())
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
        checked = set()
        for line in (root / f"{base}-SHA256SUMS.txt").read_text().splitlines():
            expected_hash, filename = line.split(None, 1)
            filename = filename.strip()
            if Path(filename).name != filename:
                raise ValueError("Checksum filename must be a plain filename")
            checked.add(filename)
            with (root / filename).open("rb") as stream:
                actual_hash = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual_hash != expected_hash:
                raise ValueError(f"Checksum mismatch: {filename}")
        required = {name for name in expected if name.startswith(base + ".")}
        if checked != required:
            raise ValueError(f"Checksum inventory does not match platform downloads: {base}")
    source = root / f"LNMTLWebToEbook-{VERSION}-source.zip"
    if not source.is_file():
        raise ValueError("Source package missing")
    return sorted(p for p in root.iterdir() if p.is_file())


def main():
    tag = os.environ.get("GITHUB_REF_NAME")
    repository = os.environ.get("GITHUB_REPOSITORY")
    if tag != "v" + VERSION or repository != REPOSITORY:
        raise ValueError("Publish only from the matching version tag in " + REPOSITORY)
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", VERSION):
        raise ValueError("Production publication requires a stable version")
    assets = verify_assets(ROOT / "release")
    view = ["gh", "release", "view", tag, "--repo", repository,
            "--json", "isDraft,isPrerelease,assets"]
    existing = subprocess.run(view, capture_output=True, text=True)
    if existing.returncode == 0:
        state = json.loads(existing.stdout)
        if not state["isDraft"] or state["isPrerelease"]:
            raise ValueError("Production publishing requires a draft; existing public releases and prereleases are kept separate")
    else:
        subprocess.run(["gh", "release", "create", tag, "--repo", repository,
                        "--verify-tag", "--draft", "--title", f"{APP_NAME} {VERSION}",
                        "--notes-file", str(ROOT / ".github" / "RELEASE_NOTES.md")], check=True)
    subprocess.run(["gh", "release", "upload", tag, "--repo", repository,
                    "--clobber", *map(str, assets)], check=True)
    uploaded = json.loads(subprocess.run(view, capture_output=True, text=True, check=True).stdout)
    verify_names(asset["name"] for asset in uploaded["assets"])
    local_sizes = {asset.name: asset.stat().st_size for asset in assets}
    remote_sizes = {asset["name"]: asset["size"] for asset in uploaded["assets"]}
    if any(remote_sizes.get(name) != size for name, size in local_sizes.items()):
        raise ValueError("Uploaded assets are incomplete or have unexpected sizes; release remains a draft")
    subprocess.run(["gh", "release", "edit", tag, "--repo", repository,
                    "--draft=false", "--prerelease=false", "--latest"], check=True)



if __name__ == "__main__":
    main()
