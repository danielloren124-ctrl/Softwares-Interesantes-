"""Downgrade workflows: safe (backup+clean install) or advanced (unsupported)."""
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from config import LOG_DIR, TEMP_DIR
from core import backup as backup_mod
from utils.logger import get_logger

logger = get_logger("downgrade_engine")


@dataclass
class Result:
    success: bool
    code: int
    log_path: str
    message: str = ""


def mode_safe(iso_drive: str, backup_path: str) -> Result:
    """Backup user data, then launch clean install (user finalises OOBE)."""
    logger.info("Starting SAFE downgrade; backup target: %s", backup_path)
    b = backup_mod.backup_user_data(backup_path)
    if not b.success:
        return Result(False, -1, b.log_path, f"Backup failed: {b.message}")

    setup_exe = Path(iso_drive) / "setup.exe"
    if not setup_exe.exists():
        return Result(False, -1, b.log_path, "setup.exe missing on ISO")

    cmd = [str(setup_exe), "/auto", "clean", "/showoobe", "none"]
    log_path = LOG_DIR / "downgrade_safe.log"
    logger.info("Running safe downgrade: %s", cmd)
    with open(log_path, "a", encoding="utf-8") as logf:
        proc = subprocess.Popen(
            cmd, stdout=logf, stderr=subprocess.STDOUT
        )
        code = proc.wait()
    return Result(
        code in (0, 3010), code, str(log_path),
        "Safe downgrade launched (complete setup manually at OOBE).",
    )


def mode_advanced(iso_drive: str) -> Result:
    """Advanced downgrade: extract ISO, patch setupconfig, run with ignorewarning."""
    logger.warning("Running ADVANCED downgrade (user assumes risk)")
    extract_dir = TEMP_DIR / "iso_extracted"
    if extract_dir.exists():
        shutil.rmtree(extract_dir, ignore_errors=True)
    extract_dir.mkdir(parents=True)
    shutil.copytree(iso_drive, extract_dir, dirs_exist_ok=True)

    sources = extract_dir / "sources"
    sources.mkdir(exist_ok=True)
    (sources / "setupconfig.ini").write_text(
        "[SetupConfig]\n"
        "Compat IgnoreWarning=On\n"
        "Migrate IgnoreWarning=On\n",
        encoding="utf-8",
    )

    setup_exe = extract_dir / "setup.exe"
    if not setup_exe.exists():
        return Result(False, -1, "", "setup.exe missing in extracted ISO")

    cmd = [
        str(setup_exe), "/auto", "upgrade",
        "/compat", "ignorewarning",
        "/migrate", "ignorewarning",
    ]
    log_path = LOG_DIR / "downgrade_advanced.log"
    logger.info("Running advanced downgrade: %s", cmd)
    with open(log_path, "a", encoding="utf-8") as logf:
        proc = subprocess.Popen(
            cmd, stdout=logf, stderr=subprocess.STDOUT
        )
        code = proc.wait()
    return Result(
        code in (0, 3010), code, str(log_path),
        "Advanced downgrade finished (may have failed; see log).",
    )
