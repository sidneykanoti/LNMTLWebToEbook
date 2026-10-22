import sys
from lnmtl.platform_support import APP_NAME, configure_runtime, user_data_directory


def main():
    configure_runtime()
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        from lnmtl.selftest import run
        return run(sys.argv[2])
    from lnmtl.gui import App
    App().mainloop()
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback
        root = user_data_directory()
        root.mkdir(parents=True, exist_ok=True)
        log = root / "startup-error.log"
        log.write_text(traceback.format_exc(), encoding="utf-8")
        from tkinter import messagebox
        messagebox.showerror(APP_NAME, f"The app could not start. Details were saved to:\n{log}")
        raise
