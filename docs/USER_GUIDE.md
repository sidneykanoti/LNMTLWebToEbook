# Using LNMTL Web to Ebook

## Install or open

Get the download for your operating system and processor from the repository's **Releases** page.

- **Windows:** open the `.exe`. Python and the PDF engine are included.
- **macOS:** use the Apple Silicon or Intel `.dmg`, then drag the app to Applications.
- **Ubuntu 24.04+ x64:** install the `.deb` using your package manager. It declares the system libraries needed by Chromium.
- **Portable Linux:** extract the `.tar.gz` and run `LNMTLWebToEbook` on a compatible graphical Linux system with the dependencies described in PACKAGING.md.

These downloads are unsigned. They are not Windows publisher-certified or Apple-notarized. Operating-system security policies may warn about or block them.

## Download your novels

1. Open **Library → Add novel**. Enter a link such as `https://lnmtl.com/novel/against-the-gods`, or the short name `against-the-gods`.
2. Select the novel in Library. Its poster, author, saved chapter count, and synopsis appear in the details panel. Search matches titles and authors.
3. Select **Download sample** for three new chapters. For full downloads, turn off **Settings → Sample mode** and select **Download**.
4. **Downloads** shows the current novel, saved chapters, percentage, and a single progress bar. **Pause** keeps saved chapters and queued work.
5. Choose EPUB, PDF, and/or HTML under **Settings → Export formats**. Select novels in Library, then choose **Export**.
6. Use **Settings → Open books folder** to find exported books.

**Load catalogue** collects the full novel list without downloading chapter text. Select multiple novels using Ctrl/Shift to process them sequentially. **Refresh details** updates the selected novel's index and metadata. A queue job can keep running while you switch views.

In **Downloads**, queue totals sit below the current novel's chapter progress. Select a queued novel to see saved errors, and expand **Show activity** for detailed messages. Activity is collapsed initially. When resuming a novel, the percentage includes all chapters already saved.

The app saves what is available on LNMTL, including novels that begin after chapter 1. It does not reconstruct absent chapters. An export made before all indexed chapters finish downloading is marked partial.

## Storage

The default data folder is:

| Operating system | Folder |
| --- | --- |
| Windows | `%LOCALAPPDATA%\LNMTLWebToEbook` |
| macOS | `~/Library/Application Support/LNMTLWebToEbook` |
| Linux | `$XDG_DATA_HOME/LNMTLWebToEbook`, or `~/.local/share/LNMTLWebToEbook` |

`library` contains the database and original chapter pages; `output` contains the books. **Settings → Choose library folder** lets you select another library. The app does not automatically import the older `LNMTLReadingLibrary` folder.

Deleting the portable executable does not delete saved books or data.

## Clear data or remove the app

**Settings → Clear app data…** offers two modes:

- Reset the active library and keep using the app. Exported books and preferences are kept unless their separate options are selected.
- Tick **Remove the app data folder completely and exit** to delete everything inside the default application-data folder, including its books and preferences, and close the app without rebuilding the empty database. Custom libraries outside that folder are kept. You can then delete the executable. Opening it again creates a fresh data folder.

Removal is permanent and requires confirmation. Close other copies of the app before clearing data.

## Help and optional support

If a website request is blocked, the app stops rather than bypassing its protection. Try again later. Website layout changes can require an app update. For an issue report, include your operating system, the app version, the novel URL, and the visible error message. Do not share account credentials or private library databases.

All features are available without paying. **Settings → Support the project** opens the project's PayPal page in your browser. The app does not handle payment details or track donations.


### Posters, authors, and synopses

Newly added or refreshed novels include the title, author, poster, and synopsis supplied by LNMTL. Exported books open with a poster/title/author page, followed by the synopsis when available, export details, and chapters. EPUB files also mark the poster as their cover for compatible reading apps. HTML and PDF include the image directly; exports need no internet connection.

For an existing novel, select it and use **Refresh details** once to collect these details, then export it again. Saved chapters are kept. If a poster cannot be downloaded, the log reports it and the book can still be exported; a previously saved poster is kept. Novels without posters or synopses remain exportable.


### Whole-catalogue downloads

Use **Download entire catalogue** to fetch the current catalogue and queue full downloads, regardless of the sample setting in Settings. To queue a subset, select novels, turn off Settings → Sample mode, then use Download. The queue is stored with the current library.

The app processes one novel at a time and saves each successful chapter immediately. Failed index, chapter, or export jobs receive up to three attempts per run, with increasing delays; other novels continue while retries wait. Export retries reuse downloaded chapters. Select a row in the Downloads queue to inspect saved errors and **Resume queue** to retry failed or unfinished jobs. Access blocks stop the queue safely.

Enable **Export each completed novel** and select the desired formats before queueing to export each fully downloaded novel. Format choices are saved per job. Enable **Resume queue when app opens** to continue unfinished work automatically on the next launch; it is initially off. Keep the computer awake during downloads. Pausing or closing keeps the queue and downloaded chapters.

The progress bar measures saved chapters in the current novel. Queue totals separately show completed novels and jobs needing attention. Completed jobs are skipped when resuming. Starting Download entire catalogue again queues all current catalogue novels again, reuses saved chapters, and applies the current export choices. Refresh a novel's index to discover chapters added since it was last indexed.
