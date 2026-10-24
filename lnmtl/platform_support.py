"""Writable user storage and desktop integration for all supported platforms."""
import json
import os
import subprocess
import sys
from pathlib import Path

APP_NAME = "LNMTL Web to Ebook"
VERSION = "1.1.0"
SUPPORT_URL = "https://www.paypal.biz/omnipotentcore"
SOURCE_ROOT = Path(__file__).resolve().parent.parent


def asset_path(name):
    return SOURCE_ROOT / "assets" / name


def user_data_directory(platform=None, home=None, environ=None):
    platform = platform or sys.platform
    home = Path(home) if home is not None else Path.home()
    env = os.environ if environ is None else environ
    if platform == "win32":
        base = Path(env.get("LOCALAPPDATA") or home / "AppData" / "Local")
    elif platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        configured = Path(env.get("XDG_DATA_HOME", ""))
        base = configured if env.get("XDG_DATA_HOME") and configured.is_absolute() else home / ".local" / "share"
    return base / "LNMTLWebToEbook"


def library_directory():
    override = os.environ.get("LNMTL_LIBRARY_DIR")
    if override:
        return Path(override).expanduser().resolve()
    preferences = user_data_directory() / "preferences.json"
    try:
        chosen = json.loads(preferences.read_text(encoding="utf-8")).get("library")
        if chosen:
            return Path(chosen).expanduser().resolve()
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    if not getattr(sys, "frozen", False):
        return SOURCE_ROOT / "library"
    return user_data_directory() / "library"


def choose_library_directory(path):
    path = Path(path).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    config = user_data_directory()
    config.mkdir(parents=True, exist_ok=True)
    pending = config / "preferences.json.tmp"
    pending.write_text(json.dumps({"library": str(path)}, indent=2), encoding="utf-8")
    pending.replace(config / "preferences.json")
    # Also take effect when the current session was started with an override.
    os.environ["LNMTL_LIBRARY_DIR"] = str(path)
    return path


def output_directory(library_root=None):
    root = Path(library_root) if library_root is not None else library_directory()
    return root.parent / "output"


def open_folder(path):
    path = Path(path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def configure_runtime():
    """Use the browser packaged alongside Playwright, independent of the user's cache."""
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(Path(sys.executable).resolve().parent.parent / "Resources" / "browsers")
        else:
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
    else:
        import importlib.util
        spec = importlib.util.find_spec("playwright")
        if spec and spec.origin:
            browsers = Path(spec.origin).parent / "driver" / "package" / ".local-browsers"
            if browsers.is_dir():
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
        # Portable Windows Python installations sometimes need these explicit paths.
        if sys.platform == "win32":
            for key, folder in (("TCL_LIBRARY", "tcl8.6"), ("TK_LIBRARY", "tk8.6")):
                location = Path(sys.base_prefix) / "tcl" / folder
                if location.is_dir():
                    os.environ.setdefault(key, str(location))
