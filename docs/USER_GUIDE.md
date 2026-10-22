# Using LNMTL Web to Ebook

## Install or open

Get the download for your operating system and processor from the repository's **Releases** page.

- **Windows:** open the `.exe`. Python and the PDF engine are included.
- **macOS:** use the Apple Silicon or Intel `.dmg`, then drag the app to Applications.
- **Ubuntu 24.04+ x64:** install the `.deb` using your package manager. It declares the system libraries needed by Chromium.
- **Portable Linux:** extract the `.tar.gz` and run `LNMTLWebToEbook` on a compatible graphical Linux system with the dependencies described in PACKAGING.md.

These downloads are unsigned. They are not Windows publisher-certified or Apple-notarized. Operating-system security policies may warn about or block them.

## Download your novels

1. Enter a novel URL such as `https://lnmtl.com/novel/against-the-gods`, or its short name `against-the-gods`.
2. Select **Add / refresh novel** to collect its available chapter index.
3. Select the novel in the list and choose **Download / resume selected**.
4. **Sample first** initially limits each run to three new chapters. Uncheck it to download all remaining chapters.
5. Select EPUB, PDF, or HTML and click **Export selected**.
6. Click **Open books folder** to find the exported books.

**Load catalogue** collects the full novel list without downloading chapter text. Select multiple novels to process them sequentially. **Pause downloads** stops safely between requests; reopening the app preserves completed downloads. A later run retries outstanding chapters. Refresh the novel index to discover newly available chapters.

The app saves what is available on LNMTL, including novels that begin after chapter 1. It does not reconstruct absent chapters. An export made before all indexed chapters finish downloading is marked partial.

## Storage

The default data folder is:

| Operating system | Folder |
| --- | --- |
| Windows | `%LOCALAPPDATA%\LNMTLWebToEbook` |
| macOS | `~/Library/Application Support/LNMTLWebToEbook` |
| Linux | `$XDG_DATA_HOME/LNMTLWebToEbook`, or `~/.local/share/LNMTLWebToEbook` |

`library` contains the database and original chapter pages; `output` contains the books. **Choose library folder** lets you select another library. The app does not automatically import the older `LNMTLReadingLibrary` folder.

Deleting the portable executable does not delete saved books or data.

## Clear data or remove the app

**Clear app data…** offers two modes:

- Reset the active library and keep using the app. Exported books and preferences are kept unless their separate options are selected.
- Tick **Remove the app data folder completely and exit** to delete everything inside the default application-data folder, including its books and preferences, and close the app without rebuilding the empty database. Custom libraries outside that folder are kept. You can then delete the executable. Opening it again creates a fresh data folder.

Removal is permanent and requires confirmation. Close other copies of the app before clearing data.

## Help and optional support

If a website request is blocked, the app stops rather than bypassing its protection. Try again later. Website layout changes can require an app update. For an issue report, include your operating system, the app version, the novel URL, and the visible error message. Do not share account credentials or private library databases.

All features are available without paying. **Donate** opens the project's PayPal page in your browser. The app does not handle payment details or track donations.
