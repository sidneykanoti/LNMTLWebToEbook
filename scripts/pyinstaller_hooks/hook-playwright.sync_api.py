"""Keep Chromium's prebuilt macOS libraries out of PyInstaller's binary rewriting."""
import sys
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("playwright", excludes=["driver/package/.local-browsers/**"] if sys.platform == "darwin" else [])
