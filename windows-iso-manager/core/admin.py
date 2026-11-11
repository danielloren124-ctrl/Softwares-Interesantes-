"""Ensure the process is running elevated (administrator)."""
import ctypes
import sys

from utils.logger import get_logger

logger = get_logger("admin")


def is_admin() -> bool:
    """Return True if the current process is elevated."""
    if sys.platform != "win32":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def ensure_admin() -> None:
    """Re-launch the current process elevated if not already admin."""
    if sys.platform != "win32":
        logger.warning("ensure_admin: not on Windows, skipping")
        return
    if is_admin():
        return
    logger.info("Elevating process…")
    params = " ".join(f'"{a}"' for a in sys.argv)
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1
        )
    except Exception as exc:
        logger.error("Failed to elevate: %s", exc)
    sys.exit(0)
