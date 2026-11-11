"""Subprocess wrapper with logging and optional no-window flag."""
import subprocess
import sys
from pathlib import Path
from typing import Optional

from utils.logger import get_logger

logger = get_logger("shell")

CREATE_NO_WINDOW: int = 0x08000000 if sys.platform == "win32" else 0


def oem_encoding() -> str:
    """Return the console (OEM) code page of this Windows install, e.g. 'cp850'.

    Native tools such as dism.exe write their output in the OEM code page, so
    decoding them with the ANSI default mangles accented characters like the
    'Í' of 'Índice' or the 'ó' of 'Versión'.
    """
    if sys.platform != "win32":
        return "utf-8"
    try:
        import ctypes
        return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
    except Exception:
        return "cp850"


def run(
    cmd: list[str],
    log_path: Optional[Path] = None,
    check: bool = False,
    no_window: bool = True,
    capture: bool = True,
    encoding: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """Run a command, redirecting output to log_path if provided."""
    kwargs: dict = {
        "capture_output": capture,
        "text": True,
        "check": check,
    }
    if encoding:
        kwargs["encoding"] = encoding
        kwargs["errors"] = "replace"
    if no_window and sys.platform == "win32":
        kwargs["creationflags"] = CREATE_NO_WINDOW
    logger.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, **kwargs)
    if log_path:
        with open(log_path, "a", encoding="utf-8") as f:
            if result.stdout:
                f.write(result.stdout)
            if result.stderr:
                f.write(result.stderr)
    logger.debug("Exit code: %s", result.returncode)
    return result
