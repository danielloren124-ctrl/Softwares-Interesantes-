"""Read current Windows version, edition, arch, language, install date."""
import datetime
import platform
import sys
from typing import Any

from utils.logger import get_logger

logger = get_logger("windows_info")

try:
    import winreg  # type: ignore
except ImportError:  # non-Windows dev
    winreg = None  # type: ignore

try:
    import psutil  # type: ignore
except ImportError:
    psutil = None  # type: ignore


def is_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception as exc:
        logger.error("is_admin failed: %s", exc)
        return False


def free_space_gb(path: str = "C:\\") -> float:
    try:
        if psutil is not None:
            return psutil.disk_usage(path).free / (1024 ** 3)
        return 0.0
    except Exception as exc:
        logger.error("free_space_gb failed: %s", exc)
        return 0.0


def on_ac_power() -> bool:
    """True if plugged in or battery >= 40 %."""
    if psutil is None:
        return True
    try:
        battery = psutil.sensors_battery()
        if battery is None:
            return True
        return bool(battery.power_plugged) or battery.percent >= 40
    except Exception as exc:
        logger.error("on_ac_power failed: %s", exc)
        return True


def _lang_id_to_tag(lang_id: int) -> str:
    mapping = {0x0409: "en-US", 0x0C0A: "es-ES", 0x080A: "es-MX"}
    return mapping.get(lang_id, f"0x{lang_id:04X}")


def get_current_version() -> dict[str, Any]:
    """Return dict {version, build, edition, arch, lang, install_date}."""
    info: dict[str, Any] = {
        "version": "unknown",
        "build": "unknown",
        "edition": "unknown",
        "arch": platform.machine(),
        "lang": "unknown",
        "install_date": "unknown",
    }
    if sys.platform != "win32" or winreg is None:
        return info
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        )
        # Modern Windows exposes real version via Major/Minor
        try:
            major, _ = winreg.QueryValueEx(key, "CurrentMajorVersionNumber")
            minor, _ = winreg.QueryValueEx(key, "CurrentMinorVersionNumber")
            info["version"] = f"{major}.{minor}"
        except OSError:
            try:
                val, _ = winreg.QueryValueEx(key, "CurrentVersion")
                info["version"] = str(val)
            except OSError:
                pass
        for name, field in [
            ("CurrentBuildNumber", "build"),
            ("EditionID", "edition"),
        ]:
            try:
                val, _ = winreg.QueryValueEx(key, name)
                info[field] = str(val)
            except OSError:
                pass
        try:
            val, _ = winreg.QueryValueEx(key, "InstallDate")
            info["install_date"] = datetime.datetime.fromtimestamp(
                int(val)
            ).isoformat()
        except OSError:
            pass
        winreg.CloseKey(key)
    except Exception as exc:
        logger.error("get_current_version failed: %s", exc)

    try:
        import ctypes
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        info["lang"] = _lang_id_to_tag(lang_id)
    except Exception:
        pass
    return info
