"""Application-wide configuration constants and paths."""
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # One-file PyInstaller build: keep logs/temp next to the .exe instead of
    # inside the temporary _MEIPASS extraction directory (which is deleted).
    BASE_DIR: Path = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent
LOG_DIR: Path = BASE_DIR / "logs"
TEMP_DIR: Path = BASE_DIR / "temp"

LOG_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

MIN_SPACE_UPGRADE_GB: float = 25.0
MIN_SPACE_DOWNGRADE_GB: float = 40.0
MIN_BATTERY: int = 40

APP_NAME: str = "Windows ISO Version Manager"
APP_VERSION: str = "1.0.0"
