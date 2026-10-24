LNMTL Web to Ebook 1.1.0 saves the chapters available on LNMTL and exports readable EPUB, PDF, and HTML books with colors, italics, and bold text preserved.


This minor release adds persistent bulk downloads while preserving existing libraries:

- Download the entire catalogue or queue selected full novels.
- Pause and resume saved jobs after interruptions; optionally resume when opening the app.
- Track overall novel/chapter progress and inspect saved errors.
- Retry failed novels and exports automatically up to three times per run while continuing other jobs.
- Optionally export each completed novel in the selected formats.
- Include posters, authors, and synopses in offline EPUB, PDF, and HTML books, with EPUB cover thumbnails.

For existing novels, refresh their index once and export again to collect posters and synopses. Saved chapters are retained. Whole-catalogue downloads ignore sample mode; the computer must stay awake and the app must remain open to download.

Choose the download for your computer:

| Computer | Download |
| --- | --- |
| Windows 10/11, Intel/AMD 64-bit | `LNMTLWebToEbook-1.1.0-windows-x64.exe` |
| Mac with Apple Silicon | `LNMTLWebToEbook-1.1.0-macos-arm64.dmg` |
| Mac with Intel processor | `LNMTLWebToEbook-1.1.0-macos-x64.dmg` |
| Ubuntu 24.04+ 64-bit | `LNMTLWebToEbook-1.1.0-linux-x64.deb` |
| Compatible Linux 64-bit, portable archive | `LNMTLWebToEbook-1.1.0-linux-x64.tar.gz` |

Python and the PDF engine are included. The portable Linux archive still needs compatible system libraries; the Ubuntu package declares its dependencies. These targets do not include Windows/Linux ARM or every Linux distribution.

Downloads are published only after the archive tests and packaged desktop/EPUB/PDF acceptance tests pass on every build platform. Checksums and the per-platform acceptance-test reports are included.

These builds are unsigned development releases. macOS builds are not Apple-notarized, and Windows or macOS security controls may warn about or block them. Passing automated tests is not equivalent to certification or testing every computer configuration.

Saved data uses the `LNMTLWebToEbook` application-data directory. Data from the older `LNMTLReadingLibrary` folder is not migrated. **Clear app data…** can reset the current library or remove the app data folder and exit. Removing the complete folder deletes books stored there too; external custom libraries are kept.

No novels or downloaded chapter data are included in these downloads. Use the tool with material you are permitted to archive.

Optional support: [Donate through PayPal](https://www.paypal.biz/omnipotentcore).
