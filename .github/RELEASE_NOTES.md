LNMTL Web to Ebook 1.2.2 saves the chapters available on LNMTL and exports readable EPUB, PDF, and HTML books with colors, italics, and bold text preserved.


This update adds two sidebar items immediately after Downloads:

- **Help:** a scrollable in-app guide to adding novels, downloading chapters, pausing and resuming queues, exporting books, storage, and troubleshooting.
- **Donate:** opens the existing project PayPal page in your default browser.

The **Support the project** button in Settings is unchanged. Existing libraries, saved chapters, preferences, and queues continue to work.

Choose the download for your computer:

| Computer | Download |
| --- | --- |
| Windows 10/11, Intel/AMD 64-bit | `LNMTLWebToEbook-1.2.2-windows-x64.exe` |
| Mac with Apple Silicon | `LNMTLWebToEbook-1.2.2-macos-arm64.dmg` |
| Mac with Intel processor | `LNMTLWebToEbook-1.2.2-macos-x64.dmg` |
| Ubuntu 24.04+ 64-bit | `LNMTLWebToEbook-1.2.2-linux-x64.deb` |
| Compatible Linux 64-bit, portable archive | `LNMTLWebToEbook-1.2.2-linux-x64.tar.gz` |

Python and the PDF engine are included. The portable Linux archive still needs compatible system libraries; the Ubuntu package declares its dependencies. These targets do not include Windows/Linux ARM or every Linux distribution.

Downloads are published only after the archive tests and packaged desktop/EPUB/PDF acceptance tests pass on every build platform. Checksums and the per-platform acceptance-test reports are included.

These builds are unsigned development releases. macOS builds are not Apple-notarized, and Windows or macOS security controls may warn about or block them. Passing automated tests is not equivalent to certification or testing every computer configuration.

Saved data uses the `LNMTLWebToEbook` application-data directory. Data from the older `LNMTLReadingLibrary` folder is not migrated. **Clear app data…** can reset the current library or remove the app data folder and exit. Removing the complete folder deletes books stored there too; external custom libraries are kept.

No novels or downloaded chapter data are included in these downloads. Use the tool with material you are permitted to archive.

Optional support: [Donate through PayPal](https://www.paypal.biz/omnipotentcore).
