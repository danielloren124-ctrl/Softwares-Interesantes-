"""Inspect ISO contents to detect version, edition, arch, language."""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from utils.logger import get_logger
from utils.shell import oem_encoding, run

logger = get_logger("iso_inspector")


@dataclass
class ISOMetadata:
    version: str = "unknown"
    build: str = "unknown"
    arch: str = "unknown"
    lang: str = "unknown"
    editions: list[str] = field(default_factory=list)
    wim_path: str = ""


# DISM devuelve la arquitectura como número (DismImageArchitecture) y
# ConvertTo-Json la serializa igual; también puede llegar como texto.
_ARCH_MAP: dict[str, str] = {
    "0": "x86",
    "5": "arm",
    "9": "x64",
    "12": "arm64",
    "x86": "x86",
    "arm": "arm",
    "x64": "x64",
    "arm64": "arm64",
    "amd64": "x64",
    "x86_64": "x64",
}


def _norm_arch(value: object) -> str:
    raw = str(value).strip().lower()
    return _ARCH_MAP.get(raw, raw or "unknown")


def _norm_lang(item: dict) -> str:
    """Idioma por defecto del objeto JSON de Get-WindowsImage.

    El objeto de DISM no tiene la propiedad 'Language': expone 'Languages'
    (lista) y 'DefaultLanguageIndex'.
    """
    lang = item.get("Language")
    if lang:
        return str(lang).strip()
    langs = item.get("Languages")
    if isinstance(langs, list) and langs:
        idx = item.get("DefaultLanguageIndex")
        if isinstance(idx, int) and 0 <= idx < len(langs):
            return str(langs[idx])
        return str(langs[0])
    return "unknown"


def _find_wim(drive_letter: str) -> Path | None:
    # drive_letter viene como "E:\\": la barra final es imprescindible para
    # que Path() apunte a la raíz de la unidad y no a "E:" (unidad relativa).
    sources = Path(drive_letter) / "sources"
    for name in ("install.wim", "install.esd"):
        candidate = sources / name
        if candidate.exists():
            return candidate
    return None


def _set_build(meta: ISOMetadata) -> None:
    if meta.version != "unknown" and "." in meta.version:
        parts = meta.version.split(".")
        if len(parts) >= 3:
            meta.build = parts[2]


def _fallback_dism(wim: Path, meta: ISOMetadata) -> None:
    """Fallback parsing for DISM if PowerShell fails or returns nulls.

    Rellena únicamente los campos que sigan en 'unknown', de modo que se puede
    llamar también para completar sólo las ediciones.
    """
    # dism.exe escribe en la página de códigos OEM: hay que decodificar con ella
    # para no romper 'Índice' / 'Versión' / 'Arquitectura'.
    enc = oem_encoding()
    res = run(["dism", "/Get-WimInfo", f"/WimFile:{wim}"], encoding=enc)
    text = res.stdout or ""

    # Busca 'Index' o 'Índice'
    indices = re.findall(r"^(?:Index|Índice)\s*:\s*(\d+)", text, re.MULTILINE)
    editions = [
        e.strip() for e in re.findall(r"^(?:Name|Nombre)\s*:\s*(.+)$", text, re.MULTILINE)
    ]
    if editions and not meta.editions:
        meta.editions = editions
    if not indices:
        return

    detail = run(
        ["dism", "/Get-WimInfo", f"/WimFile:{wim}", f"/Index:{indices[0]}"],
        encoding=enc,
    )
    t = detail.stdout or ""

    def _match(key_eng, key_esp):
        # Busca la etiqueta en inglés o español
        m = re.search(rf"^(?:{key_eng}|{key_esp})\s*:\s*(.+)$", t, re.MULTILINE | re.IGNORECASE)
        return m.group(1).strip() if m else "unknown"

    if meta.version == "unknown":
        meta.version = _match("Version", "Versión")
    if meta.arch == "unknown":
        meta.arch = _norm_arch(_match("Architecture", "Arquitectura"))
    if meta.lang == "unknown":
        meta.lang = _match("Language", "Idioma") or _match(
            "Default Language", "Idioma predeterminado"
        )
    _set_build(meta)


def inspect(drive_letter: str) -> ISOMetadata:
    """Inspect an ISO mounted at drive_letter."""
    meta = ISOMetadata()
    wim = _find_wim(drive_letter)
    if not wim:
        logger.warning("No install.wim/esd found at %s", drive_letter)
        return meta
    meta.wim_path = str(wim)

    # 1. Intentar con PowerShell (más rápido y estructurado).
    #    Sin '-Index 1' para obtener todas las ediciones de la ISO de una vez.
    script = (
        f"Get-WindowsImage -ImagePath '{wim}' | "
        f"Select-Object ImageName, Version, Architecture, Language, "
        f"Languages, DefaultLanguageIndex | "
        f"ConvertTo-Json -Compress"
    )
    res = run(["powershell", "-NoProfile", "-Command", script])
    out = (res.stdout or "").strip()

    if out and res.returncode == 0:
        try:
            data = json.loads(out)
            items = data if isinstance(data, list) else [data]
            first = items[0] if items else {}

            v = first.get("Version")
            a = first.get("Architecture")

            if v and a is not None:
                meta.version = str(v)
                meta.arch = _norm_arch(a)
                meta.lang = _norm_lang(first)
                meta.editions = [
                    str(d["ImageName"]) for d in items if d.get("ImageName")
                ]
                _set_build(meta)
            else:
                logger.warning("PowerShell devolvió datos incompletos. Usando DISM...")
                _fallback_dism(wim, meta)

        except Exception as exc:
            logger.error("Failed to parse WIM JSON: %s", exc)
            _fallback_dism(wim, meta)
    else:
        # 2. Si PowerShell falla (ej. Windows antiguo), usar DISM
        logger.warning("PowerShell falló. Usando DISM...")
        _fallback_dism(wim, meta)

    # 3. Última pasada: completar lo que siga faltando (típicamente ediciones)
    if not meta.editions or meta.lang == "unknown" or meta.arch == "unknown":
        logger.warning("Datos incompletos tras PowerShell. Completando con DISM...")
        _fallback_dism(wim, meta)

    logger.info("ISO metadata: %s", meta)
    return meta
