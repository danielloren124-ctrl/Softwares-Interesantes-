"""Backup user profile and drivers with robocopy / pnputil."""
import os
from dataclasses import dataclass
from pathlib import Path

from utils.logger import get_logger
from utils.shell import run

logger = get_logger("backup")


@dataclass
class Result:
    success: bool
    log_path: str
    message: str = ""


EXCLUDES = [
    r"\AppData\Local\Temp",
    r"\AppData\Local\Microsoft\Windows\INetCache",
    r"\AppData\Local\Microsoft\Windows\Explorer",
    r"\AppData\Local\Packages",
]


def _profile_path() -> Path:
    return Path(os.environ.get("USERPROFILE", str(Path.home())))


def backup_user_data(dest: str) -> Result:
    dest_path = Path(dest)
    dest_path.mkdir(parents=True, exist_ok=True)
    src = str(_profile_path())
    log_path = dest_path / "backup.log"
    cmd = [
        "robocopy", src, str(dest_path),
        "/MIR", "/R:1", "/W:1", "/XJ",
        "/NFL", "/NDL", "/NP",
    ]
    for ex in EXCLUDES:
        cmd.extend(["/XD", src + ex])
    logger.info("Running backup with robocopy to %s", dest_path)
    try:
        proc = run(cmd, log_path=log_path)
        ok = proc.returncode < 8  # robocopy >=8 is a real failure
        return Result(ok, str(log_path), f"robocopy exit {proc.returncode}")
    except Exception as exc:
        logger.exception("Backup failed")
        return Result(False, str(log_path), str(exc))


def list_drivers(dest: str) -> Path:
    """Export third-party drivers to dest/drivers."""
    dest_path = Path(dest) / "drivers"
    dest_path.mkdir(parents=True, exist_ok=True)
    run(["pnputil", "/export-driver", "*", str(dest_path)])
    return dest_path
