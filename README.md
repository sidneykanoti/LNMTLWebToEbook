# LNMTL Web to Ebook

![LNMTL Web to Ebook icon](assets/app-128.png)

[Website](https://lnmtl-web-to-ebook.pages.dev/) | [Downloads](https://github.com/sidneykanoti/LNMTLWebToEbook/releases) | [User guide](docs/USER_GUIDE.md) | [Donate](https://www.paypal.biz/omnipotentcore)

A free, independent desktop downloader for whole novels listed on lnmtl.com, with EPUB, PDF, and HTML exports. Select novels, not individual chapters; turn off **Settings → Sample mode** to download all available indexed chapters. Downloads and original chapter pages stay on your computer.

## Open the app

Download the version for your computer from the repository's **Releases** page. Python and the PDF engine are included. The release workflow builds and tests Windows x64, macOS Apple Silicon, macOS Intel, and Ubuntu 24.04+ x64 before publishing. See [PACKAGING.md](PACKAGING.md) for platform support and instructions.

For this source checkout, double-click **Start Library.cmd**. On a fresh Windows machine, install Python 3.13 with Tk support, then run **Setup.cmd** once. On macOS/Linux, install the requirements into a virtual environment, set `PLAYWRIGHT_BROWSERS_PATH=0` while installing `python -m playwright install chromium --only-shell`, and run `python app.py` using that environment. Linux also requires Chromium's system libraries.

1. In **Library**, choose **Add novel**, paste an LNMTL link or short name, and confirm. The app collects its chapter index, author, poster, and synopsis.
2. Select a novel to see its poster and synopsis in the details panel. Search by title or author.
3. Choose **Download sample** to save three new chapters, or turn off sample mode in **Settings** and choose **Download** to queue the full novel.
4. Follow progress in **Downloads**, where one progress bar shows the current novel's saved chapters and percentage. Use **Pause** to stop safely.
5. Choose export formats in **Settings**, then select novels in Library and click **Export**. Find results through **Settings → Open books folder**.

**Load catalogue** collects the full novel list without downloading chapters. Ctrl/Shift selection lets you choose several novels. **Refresh details** updates the selected novel's chapter index and metadata while preserving saved chapters. Existing libraries and queues continue to work.

## Archive the whole catalogue

Choose **Download entire catalogue** to collect all novels and download their indexed chapters sequentially. This downloads full novels even when **Settings → Sample mode** is enabled. The queue is saved in the current library and skips chapters already downloaded.

- **Resume queue** continues after a pause or interruption. Completed jobs are skipped; failed novels get up to three more attempts.
- **Resume queue when app opens** enables automatic continuation on the next launch. It is off initially. The computer must remain awake and the app must be open to make progress.
- **Export each completed novel** saves books automatically using the selected EPUB/PDF/HTML formats. These choices are saved with each queued novel and survive restarts. Partial novels are not automatically exported; manual export remains available.
- Overall progress shows completed novels, failures, and saved chapters across indexed novels. The chapter total grows as more novels are indexed; it is not a fixed whole-site total at startup.
- Select a row in the Downloads queue to see saved errors. **Show activity** expands the detailed log. A failed novel does not stop others. Site access blocks stop the queue; no protection is bypassed.

The app keeps one queue runner per library and bounds the on-screen log for long sessions. Whole-site archives can take days and substantial disk space. The queue, chapter index, and downloads remain local.

## Support this project

The app is free to use. Feel free to donate if you've found this software useful. The **Support the project** button in Settings opens [the project's PayPal page](https://www.paypal.biz/omnipotentcore) in your default browser. All features remain available without contributing. Payments are handled on PayPal's website; the app does not collect payment details or track contributions.

The support link is in **Settings**, away from the download controls.

## Clear app data

In **Settings**, choose **Clear app data…** to reset the current library's catalogue, index, chapter pages, and progress. Exported books are kept by default. The dialog has separate options to remove app-generated EPUB/PDF/HTML exports and to reset saved preferences/startup logs. Review the file count, size, and library path, then confirm removal. Cancel leaves everything unchanged. Close other copies of the app before clearing data. The software itself and unrelated files are not removed. Other libraries you previously chose are not cleared automatically.

After clearing, an empty library is initialized so the app remains ready to use. Temporary runtime files belonging to a running standalone executable are managed by its packager and are normally removed when the executable closes.

To prepare for removing the portable app, tick **Remove the app data folder completely and exit**. After confirmation, the entire `LNMTLWebToEbook` application-data folder is deleted and the app exits without creating a new database. This includes all files inside that folder, including exported books and preferences. Custom libraries outside this folder are kept. Close other app copies first. Delete the executable afterward; opening it again creates a fresh data folder.

## Interface

The sidebar separates **Library**, **Downloads**, and **Settings**. Library shows poster thumbnails with titles and authors, plus selected-book details. Downloads shows current chapter progress, a saved queue, and an activity log that stays collapsed until requested. Settings holds sample mode, export formats, automatic export/resume, library storage, support, and data cleanup. Preferences are saved in the active library. A job can keep running while you browse other views.

## Reading and styling

- Georgia with a serif fallback, comfortable paragraph spacing, volume headings, and linked chapter contents.
- Blue glossary terms and green modified words, using LNMTL's light-background colors.
- LNMTL's `dq`, `sq`, and `da` tags become italic, bold, and heavy bold text. Ordinary bold/italic markup and safe inline color/emphasis are retained.
- English paragraphs only; Chinese tooltip text, ads, comments, and navigation are excluded.
- EPUB readers may override fonts or publisher colors; enable publisher styling if needed. Georgia must be installed on the reading device or its serif fallback is used.
- PDFs use bundled Chromium's print renderer, A5 pages, and page numbers. Microsoft Edge is not required. PDF exports of extremely large novels may require more memory; EPUB is recommended for large books.

## Storage

`library/archive.sqlite3` stores the index, cleaned chapter HTML, download timestamps, checksums, errors, and catalogue. `library/raw/` keeps original successful chapter pages for future recovery. Back up the entire `library` folder. `output/<novel>/` contains books and `archive-report.json`, listing included chapters and outstanding downloads. Packaged versions place these folders in the user's application-data directory. Source checkouts retain workspace storage by default. **Choose library folder** lets the standalone app continue an existing source library without copying or deleting anything; see [PACKAGING.md](PACKAGING.md) for exact paths.

The application preserves all successfully saved chapters, including chapters that disappear from a later index. It does not invent missing chapters or translate new text. A complete download means all chapters indexed from LNMTL have been saved, not necessarily the author's entire novel.

## Download behavior

One request at a time, at least two seconds between request starts, with bounded retries and backoff. A blocked request stops the job rather than attempting to bypass protection. Queued novels are retried automatically up to three times per run, with waits between attempts while other novels continue. **Resume queue** retries unfinished and failed jobs. Indexing is committed only after every volume has passed its reported chapter-count checks. A cancelled index can be restarted; completed chapter downloads are committed individually.

The app is local software, not a public web service. No account or cloud upload is required. Choose **Download entire catalogue** to load the full catalogue and save a persistent full-download queue. This button ignores sample mode. With sample mode off in **Settings**, **Download** in Library also queues selected novels.

## Command-line use

```powershell
.venv/Scripts/python.exe -m lnmtl index against-the-gods
.venv/Scripts/python.exe -m lnmtl download against-the-gods --limit 3
.venv/Scripts/python.exe -m lnmtl export against-the-gods --format epub pdf html
.venv/Scripts/python.exe -m lnmtl status
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Use `--library <directory>` before the command for a separate archive. The app and command-line interface share the same default library. Run a single download job at a time.

## Current limits

Releases support only the operating systems and CPU architectures listed in the user guide. Public distribution signing/notarization is not configured. There is no automated Cloudflare challenge handling. Source HTML/API changes may require parser updates. The default colors reflect LNMTL's published light reading theme rather than individual browser theme customizations. PDFs have a linked contents page; the EPUB has volume-grouped navigation. Posters, authors, and synopses are collected when adding or refreshing novels, then embedded in exported books for offline reading.

## License

Copyright (C) 2026 Sidney Kanoti. Licensed under **GPL-3.0-only**; see [LICENSE](LICENSE). Distributed without warranty. Third-party components retain their licenses. The software license grants no rights to downloaded novels or translations. This is an independent project and is not affiliated with LNMTL.
