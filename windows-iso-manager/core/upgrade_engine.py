"""Run in-place upgrade from the mounted ISO."""
import subprocess
from dataclasses import dataclass
from pathlib import Path

from config import LOG_DIR, TEMP_DIR
from utils.logger import get_logger

logger = get_logger("upgrade_engine")


@dataclass
class Result:
    success: bool
    code: int
    log_path: str
    message: str = ""


SETUPCONFIG_TEMPLATE = """[SetupConfig]
Migrate="true"
DynamicUpdate="disable"
ShowOOBE="none"
Resize="off"
"""


def run_upgrade(
    iso_drive: str, keep_files: bool = True, keep_apps: bool = True
) -> Result:
    """Run setup.exe /auto upgrade from the mounted ISO."""
    setup_exe = Path(iso_drive) / "setup.exe"
    if not setup_exe.exists():
        return Result(False, -1, "", f"setup.exe not found at {setup_exe}")

    log_path = LOG_DIR / "upgrade.log"
    cfg = TEMP_DIR / "setupconfig.ini"
    cfg.write_text(SETUPCONFIG_TEMPLATE, encoding="utf-8")

    cmd = [
        str(setup_exe),
        "/auto", "upgrade",
        "/migratedrivers", "all",
        "/showoobe", "none",
        "/dynamicupdate", "disable",
    ]
    logger.info("Running upgrade: %s", cmd)
    with open(log_path, "a", encoding="utf-8") as logf:
        proc = subprocess.Popen(
            cmd, stdout=logf, stderr=subprocess.STDOUT
        )
        code = proc.wait()

    success = code in (0, 3010)
    return Result(success, code, str(log_path), "Upgrade finished")
