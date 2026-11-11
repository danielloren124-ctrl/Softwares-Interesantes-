"""Entry point for Windows ISO Version Manager."""
import sys
from tkinter import messagebox

from core import admin
from utils.logger import get_logger

logger = get_logger("main")


def main() -> int:
    admin.ensure_admin()
    try:
        from ui.main_window import MainWindow
        app = MainWindow()
        app.mainloop()
        return 0
    except Exception as exc:
        logger.exception("Fatal error")
        try:
            messagebox.showerror("Error fatal", str(exc))
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
