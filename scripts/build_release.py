"""Build and verify a native release on Windows, macOS, or Linux.

Run with the project's Python environment, on the operating system being packaged.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lnmtl.platform_support import VERSION, configure_runtime

NAME = "LNMTLWebToEbook"


def command(args, **kwargs):
    print("Running:", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True, cwd=ROOT, **kwargs)


def notices(path):
    lines = ["# Third-party components", "", "This application bundles Python, Tcl/Tk, Chromium Headless Shell, and these Python packages.",
             "Chromium and Playwright license/notice files are retained in their bundled directories.", "Python and Tcl/Tk license files are included by PyInstaller.", ""]
    for name in ("beautifulsoup4", "soupsieve", "requests", "urllib3", "idna", "certifi", "charset-normalizer", "playwright", "pyee", "greenlet", "pillow"):
        dist = importlib.metadata.distribution(name)
        lines += [f"## {name} {dist.version}", ""]
        files = [f for f in dist.files or [] if any(p.lower().startswith(("license", "copying", "notice")) for p in f.parts[-2:])]
        if not files:
            lines += [dist.metadata.get("License-Expression") or dist.metadata.get("License") or "See the upstream distribution for license terms.", ""]
        for file in files:
            try:
                lines += [dist.locate_file(file).read_text(encoding="utf-8"), ""]
            except (OSError, UnicodeError):
                continue
    content = "\n".join(lines)
    if not path.exists() or path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8")


def zip_folder(folder, output):
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for item in sorted(folder.rglob("*")):
            if item.is_file():
                z.write(item, item.relative_to(folder.parent))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-browser-install", action="store_true", help="Use an already-installed package-local Chromium shell")
    args = parser.parse_args()
    if sys.platform not in ("win32", "darwin", "linux"):
        parser.error("This platform is not supported.")
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
    configure_runtime()
    if not args.skip_browser_install:
        command([sys.executable, "-m", "playwright", "install", "chromium", "--only-shell"])
    import playwright
    browser_root = Path(playwright.__file__).parent / "driver" / "package" / ".local-browsers"
    if not any(browser_root.glob("chromium_headless_shell-*")):
        raise RuntimeError("The package-local Chromium headless shell is missing. Run the build without --skip-browser-install.")
    release = ROOT / "release"
    release.mkdir(exist_ok=True)
    work = ROOT / "build" / "packaging"
    work.mkdir(parents=True, exist_ok=True)
    notice_file = work / "THIRD_PARTY_NOTICES.md"
    notices(notice_file)
    # Explicit source list: private downloaded novels, databases, and existing outputs are never bundled.
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--noupx", "--name", NAME,
           "--distpath", ROOT / "dist", "--workpath", work / "pyinstaller", "--specpath", work,
           "--additional-hooks-dir", ROOT / "scripts" / "pyinstaller_hooks", "--add-data", f"{notice_file}:.",
           "--add-data", f"{ROOT / 'PACKAGING.md'}:.", "--add-data", f"{ROOT / 'README.md'}:.",
           "--add-data", f"{ROOT / 'assets'}:assets"]
    for legal_file in ("LICENSE", "NOTICE"):
        if (ROOT / legal_file).is_file():
            cmd += ["--add-data", f"{ROOT / legal_file}:."]
    if sys.platform == "win32":
        version_file = work / "windows-version.txt"
        version_tuple = tuple(int(part) for part in VERSION.split(".")) + (0,)
        version_file.write_text(f"VSVersionInfo(ffi=FixedFileInfo(filevers={version_tuple},prodvers={version_tuple},mask=0x3f,flags=0,OS=0x40004,fileType=0x1,subtype=0,date=(0,0)),kids=[StringFileInfo([StringTable('040904B0',[StringStruct('FileDescription','LNMTL Web to Ebook'),StringStruct('ProductName','LNMTL Web to Ebook'),StringStruct('FileVersion','{VERSION}'),StringStruct('ProductVersion','{VERSION}'),StringStruct('OriginalFilename','LNMTLWebToEbook.exe')])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])", encoding="utf-8")
        cmd += ["--icon", ROOT / "assets" / "app.ico", "--version-file", version_file]
    if sys.platform == "darwin":
        cmd += ["--onedir", "--osx-bundle-identifier", "com.lnmtlwebtoebook.desktop", "--icon", ROOT / "assets" / "app.icns"]
        if os.environ.get("MACOS_SIGNING_IDENTITY"):
            cmd += ["--codesign-identity", os.environ["MACOS_SIGNING_IDENTITY"]]
    else:
        cmd += ["--onefile"]
    cmd += [ROOT / "app.py"]
    command(cmd)
    if sys.platform == "darwin":
        # Preserve Chromium's load commands. PyInstaller cannot rewrite some vendor
        # dylibs because their Mach-O headers have no spare load-command space.
        app_bundle = ROOT / "dist" / f"{NAME}.app"
        command(["ditto", browser_root, app_bundle / "Contents" / "Resources" / "browsers"])
        command(["codesign", "--force", "--deep", "--sign", os.environ.get("MACOS_SIGNING_IDENTITY", "-"), app_bundle])
    system = {"win32": "windows", "darwin": "macos", "linux": "linux"}[sys.platform]
    machine = platform.machine().lower()
    architecture = {"amd64": "x64", "x86_64": "x64", "aarch64": "arm64"}.get(machine, machine)
    tag = f"{NAME}-{VERSION}-{system}-{architecture}"
    if sys.platform == "win32":
        executable = ROOT / "dist" / f"{NAME}.exe"
    elif sys.platform == "darwin":
        executable = ROOT / "dist" / f"{NAME}.app" / "Contents" / "MacOS" / NAME
    else:
        executable = ROOT / "dist" / NAME
    smoke = work / f"smoke-{system}-{architecture}"
    smoke_command = [executable, "--self-test", smoke]
    if sys.platform == "linux" and not os.environ.get("DISPLAY"):
        if not shutil.which("xvfb-run"):
            raise RuntimeError("Install xvfb to test the Linux GUI on a headless build machine.")
        smoke_command = ["xvfb-run", "-a", *smoke_command]
    # Clean DISPLAY/Python paths and browser cache overrides would reveal accidental developer dependencies.
    smoke_env = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "TCL_LIBRARY", "TK_LIBRARY", "PLAYWRIGHT_BROWSERS_PATH", "LNMTL_LIBRARY_DIR"):
        smoke_env.pop(name, None)
    command(smoke_command, env=smoke_env, timeout=180)
    report = json.loads((smoke / "self-test.json").read_text(encoding="utf-8"))
    if not report.get("passed"):
        raise RuntimeError(f"Packaged acceptance test failed: {report}")
    artifacts = []
    if sys.platform == "win32":
        target = release / f"{tag}.exe"
        shutil.copy2(executable, target)
        artifacts.append(target)
    elif sys.platform == "darwin":
        staging = work / "dmg"
        staging.mkdir(exist_ok=True)
        app = ROOT / "dist" / f"{NAME}.app"
        # ditto retains the framework and browser symlinks in the app bundle.
        command(["ditto", app, staging / app.name])
        link = staging / "Applications"
        if not link.exists():
            link.symlink_to("/Applications", target_is_directory=True)
        target = release / f"{tag}.dmg"
        command(["hdiutil", "create", "-volname", "LNMTL Web to Ebook", "-srcfolder", staging, "-ov", "-format", "UDZO", target])
        artifacts.append(target)
    else:
        target = release / f"{tag}.tar.gz"
        with tarfile.open(target, "w:gz") as archive:
            archive.add(executable, arcname=NAME)
            archive.add(notice_file, arcname="THIRD_PARTY_NOTICES.md")
            archive.add(ROOT / "PACKAGING.md", arcname="PACKAGING.md")
        artifacts.append(target)
        if shutil.which("dpkg-deb"):
            # Ubuntu 24.04+ x64/arm64 package; browser still uses the OS's shared system libraries.
            package = work / "deb"
            binary = package / "opt" / "lnmtl-reading-library" / NAME
            binary.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(executable, binary)
            binary.chmod(0o755)
            shortcut = package / "usr" / "share" / "applications" / "lnmtl-reading-library.desktop"
            shortcut.parent.mkdir(parents=True, exist_ok=True)
            shortcut.write_text(f"[Desktop Entry]\nType=Application\nName=LNMTL Web to Ebook\nExec=/opt/lnmtl-reading-library/{NAME}\nIcon=lnmtl-web-to-ebook\nTerminal=false\nCategories=Office;Literature;\n", encoding="utf-8")
            icon = package / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps" / "lnmtl-web-to-ebook.png"
            icon.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "assets" / "app-256.png", icon)
            control = package / "DEBIAN" / "control"
            control.parent.mkdir(exist_ok=True)
            deb_arch = {"x64": "amd64", "arm64": "arm64"}[architecture]
            deps = "libc6 (>= 2.39), libnss3, libnspr4, libdbus-1-3, libatk1.0-0t64, libatk-bridge2.0-0t64, libcups2t64, libdrm2, libxkbcommon0, libatspi2.0-0t64, libx11-6, libxcomposite1, libxdamage1, libxext6, libxfixes3, libxrandr2, libgbm1, libxcb1, libpango-1.0-0, libcairo2, libasound2t64, libglib2.0-0t64, libfontconfig1, libxrender1, libxss1, xdg-utils, fonts-liberation"
            control.write_text(f"Package: lnmtl-reading-library\nVersion: {VERSION}\nArchitecture: {deb_arch}\nMaintainer: LNMTL Web to Ebook maintainers\nDepends: {deps}\nSection: text\nPriority: optional\nDescription: Offline reading library and EPUB/PDF exporter for LNMTL\n", encoding="utf-8")
            target = release / f"{tag}.deb"
            command(["dpkg-deb", "--root-owner-group", "--build", package, target])
            artifacts.append(target)
    shutil.copy2(notice_file, release / "THIRD_PARTY_NOTICES.md")
    shutil.copy2(smoke / "self-test.json", release / f"{tag}-self-test.json")
    checksums = []
    for artifact in artifacts:
        with artifact.open("rb") as stream:
            checksums.append(f"{hashlib.file_digest(stream, 'sha256').hexdigest()}  {artifact.name}")
    (release / f"{tag}-SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    from package_source import package_source
    package_source()
    print("Release verified:", *artifacts, sep="\n", flush=True)


if __name__ == "__main__":
    main()
