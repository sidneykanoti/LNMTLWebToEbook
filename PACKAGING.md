# Standalone desktop releases

The same Python source is packaged separately on each operating system. The package contains Python, Tcl/Tk, the application libraries, and Chromium Headless Shell for PDF rendering. End users do not install Python, Edge, or Playwright. Internet is needed to fetch novels, but local exports work offline.

## End-user downloads

| Target | Download | How to open |
| --- | --- | --- |
| Windows 10/11 x64 | `LNMTLWebToEbook-1.0.0-windows-x64.exe` | Double-click the portable executable. No installer or administrator access is needed. |
| macOS Apple Silicon | `LNMTLWebToEbook-1.0.0-macos-arm64.dmg` | Open the disk image and drag the app to Applications. |
| macOS Intel | `LNMTLWebToEbook-1.0.0-macos-x64.dmg` | Same, using the Intel build. |
| Ubuntu 24.04+ x64 | `.deb` or `.tar.gz` | Install the Debian package with the system's package installer, or extract and run the executable. |

Linux is not a universal binary for every distribution. The first Linux target is Ubuntu 24.04+ x64; other distributions need compatible glibc and Chromium's system libraries. The `.deb` declares these dependencies. The portable tarball requires them to be installed already. A graphical desktop is required. No ARM Linux/Windows artifact is currently configured.

Windows and Linux use a single-file executable that extracts its bundled runtime into a temporary directory on launch. First startup can take a little time. macOS uses a normal `.app` bundle in a single `.dmg` download to preserve framework structure. The download is relatively large because it includes the PDF engine.

## Saved data and existing libraries

Packaged apps store their library and exported books outside the executable, under:

- Windows: `%LOCALAPPDATA%\LNMTLWebToEbook\`
- macOS: `~/Library/Application Support/LNMTLWebToEbook/`
- Linux: `$XDG_DATA_HOME/LNMTLWebToEbook/`, or `~/.local/share/LNMTLWebToEbook/`

The `library/` child contains the SQLite database and raw pages; `output/` contains exported books. Replacing the application does not replace these folders. Source checkouts retain their existing workspace storage unless a different library has been chosen.

The storage directory is now `LNMTLWebToEbook`. Earlier `LNMTLReadingLibrary` folders and preferences are not read, migrated, or removed. Use **Clear app data…** to clear the active library, optionally including its exported books and saved preferences. No recursive deletion of a chosen user directory is performed.

To continue the library from the original project, click **Choose library folder** and select the project's `library` directory (the directory containing `archive.sqlite3`). Nothing is copied or removed. Books are written to its sibling `output` directory. This selection is remembered. Back up the whole library directory to transfer it to another computer. `LNMTL_LIBRARY_DIR` can explicitly select a library directory for scripts or portable usage.

Packages never contain your downloaded novels, current database, sample books, or personal preferences. The offline test creates a small synthetic book in the build directory only.

## Build locally

Run these steps on the OS/CPU you want to distribute for. Use an official Python 3.13 installation with Tk support.

```text
python -m venv .venv
# Activate .venv using the command appropriate to your shell.
python -m pip install -r requirements-build.txt
python -m unittest discover -s tests -v
python scripts/build_release.py
```

On a headless Ubuntu build machine, also install `python3-tk`, `xvfb`, `xdg-utils`, and `fonts-liberation`, then run `python -m playwright install-deps chromium` to install browser system dependencies. Tk must also be present in the Python used by PyInstaller. On macOS, use a Python distribution that includes Tcl/Tk; Homebrew Python may require its matching `python-tk` package.

The build downloads the Chromium headless shell into Playwright's package-local browser directory and uses the official Playwright PyInstaller hook. It then builds the actual executable and runs it with `--self-test <directory>`. That test checks the desktop window, writable SQLite storage, styled EPUB, and PDF creation with packaged Chromium. A failed test prevents a release from being copied into `release/`.

Outputs in `release/` include the platform download, SHA-256 checksums, third-party notices, and the packaged acceptance-test report. Native build intermediates are in `dist/` and `build/`.

## Automated builds

`.github/workflows/build.yml` builds Windows x64, macOS ARM64, macOS Intel, and Ubuntu 24.04 x64 on their respective GitHub runners. It runs on manual dispatch or a `v*` tag. Manual runs save download artifacts. A version tag matching the app version, such as `v1.0.0`, also publishes a GitHub Release after all four targets pass. The publish job verifies the platform reports and checksums before uploading. Downloaded novels, local databases, settings, and the working virtual environment are excluded. Mac/Linux downloads cannot be built or tested natively from the Windows workspace.

## Signing and distribution status

Local builds are unsigned development releases. Windows may show an unknown-publisher notice. macOS public distribution needs Developer ID signing and Apple notarization; neither is performed without the owner's certificates/account. The optional `MACOS_SIGNING_IDENTITY` build environment variable enables PyInstaller signing using an identity already available in the build machine's keychain. This does not by itself perform notarization. Do not treat unsigned macOS workflow artifacts as a finished public release.

The Windows executable produced here is locally tested, not yet tested on a separate clean Windows installation. Mac/Linux are prepared build targets until their workflows run and their downloads are tested on those platforms.

## Official references

- [PyInstaller usage](https://pyinstaller.org/en/stable/usage.html)
- [PyInstaller runtime paths](https://pyinstaller.org/en/stable/runtime-information.html)
- [Playwright browser bundling](https://playwright.dev/python/docs/library#pyinstaller)
- [GitHub hosted build runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
