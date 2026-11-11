"""Compatibility checks executed before running setup."""
import sys

from config import MIN_BATTERY, MIN_SPACE_DOWNGRADE_GB, MIN_SPACE_UPGRADE_GB
from core.iso_inspector import inspect as inspect_iso
from core.windows_info import (
    free_space_gb,
    get_current_version,
    is_admin,
    on_ac_power,
)
from utils.logger import get_logger

logger = get_logger("validators")


def _version_tuple(v: str) -> tuple:
    parts = []
    for x in v.split("."):
        try:
            parts.append(int(x))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _build_number(value: str) -> int | None:
    """Extrae el número de build ('19043' / '19043.1052' / 'unknown')."""
    head = str(value).split(".")[0]
    return int(head) if head.isdigit() else None


def validate_environment(action: str = "upgrade") -> list[str]:
    """Return list of environment-level problems."""
    errors: list[str] = []
    if sys.platform != "win32":
        errors.append("La aplicación solo se ejecuta en Windows.")
    if not is_admin():
        errors.append("La aplicación debe ejecutarse como administrador.")
    need = MIN_SPACE_UPGRADE_GB if action == "upgrade" else MIN_SPACE_DOWNGRADE_GB
    free = free_space_gb("C:\\")
    if free < need:
        errors.append(
            f"Espacio libre insuficiente en C: {free:.1f} GB (mínimo {need:.0f} GB)."
        )
    if not on_ac_power():
        errors.append(
            f"Conecte el equipo a corriente o cargue la batería (≥{MIN_BATTERY} %)."
        )
    return errors


def validate_iso(drive: str, action: str = "upgrade") -> list[str]:
    """Return list of ISO compatibility errors, or [] if OK."""
    errors: list[str] = []
    if not drive:
        return ["ISO no montada."]
    meta = inspect_iso(drive)
    if meta.version == "unknown" and not meta.editions:
        errors.append("No se pudo leer información de install.wim/esd.")
        return errors
    cur = get_current_version()
    if cur["arch"].lower() not in ("amd64", "x86_64"):
        errors.append(f"Arquitectura actual no soportada: {cur['arch']}.")
    if meta.arch.lower() not in ("x64", "amd64", "x86_64"):
        errors.append(f"Arquitectura de ISO no soportada: {meta.arch}.")
    if (
        action == "upgrade"
        and meta.version != "unknown"
        and cur["version"] != "unknown"
    ):
        # El número de build es el que manda: "10.0" es igual para Windows 10 y
        # 11, así que comparar sólo Major.Minor no distingue versiones.
        iso_build = _build_number(meta.build)
        cur_build = _build_number(cur["build"])
        if iso_build is not None and cur_build is not None:
            older = iso_build < cur_build
        else:
            older = _version_tuple(meta.version) < _version_tuple(cur["version"])
        if older:
            errors.append(
                f"La ISO ({meta.version}, build {meta.build}) es más antigua "
                f"que el sistema ({cur['version']}, build {cur['build']}). "
                f"Use la opción Downgrade."
            )
    if meta.lang != "unknown" and cur["lang"] != "unknown":
        if meta.lang.lower()[:2] != cur["lang"].lower()[:2]:
            errors.append(
                f"Idioma ISO ({meta.lang}) distinto al del sistema ({cur['lang']})."
            )
    return errors
