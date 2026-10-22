"""Create a small build-source archive without user libraries or downloaded books."""
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lnmtl.platform_support import VERSION


def package_source():
    release = ROOT / "release"
    release.mkdir(exist_ok=True)
    path = release / f"LNMTLWebToEbook-{VERSION}-source.zip"
    selected = [ROOT / name for name in ("app.py", "requirements.txt", "requirements-build.txt", "README.md", "PACKAGING.md", ".gitignore", "Setup.cmd", "Start Library.cmd")]
    selected.extend(ROOT / name for name in ("LICENSE", "NOTICE", ".gitattributes") if (ROOT / name).is_file())
    for name in ("lnmtl", "scripts", "tests", ".github", "assets", "docs"):
        selected.extend(p for p in (ROOT / name).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for item in sorted(selected):
            z.write(item, item.relative_to(ROOT))
    with path.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    path.with_suffix(".zip.sha256").write_text(f"{checksum}  {path.name}\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(package_source())
