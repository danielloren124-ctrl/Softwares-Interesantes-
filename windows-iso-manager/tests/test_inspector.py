"""Offline checks for core.iso_inspector parsing and ISO validation."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import iso_inspector  # noqa: E402
from utils import validators  # noqa: E402

FAKE = Path("temp/fake_iso")
(FAKE / "sources").mkdir(parents=True, exist_ok=True)
(FAKE / "sources" / "install.wim").write_bytes(b"\0" * 16)

DISM_LIST = """
Herramienta de administración y mantenimiento de imágenes de implementación
Versión: 10.0.19041.1

Detalles de la imagen: E:\\sources\\install.wim

Índice: 1
Nombre: Windows 10 Pro
Descripción: Windows 10 Pro

Índice: 2
Nombre: Windows 10 Home
Descripción: Windows 10 Home
"""

DISM_DETAIL = """
Índice: 1
Nombre: Windows 10 Pro
Versión: 10.0.19043.1052
Arquitectura: x64
Idioma: es-ES
"""


def make_run(json_payload=None, json_rc=0, dism_ok=True):
    """Fake utils.shell.run for PowerShell JSON + dism calls."""
    def _run(cmd, **kw):
        joined = " ".join(cmd)
        if "Get-WindowsImage" in joined:
            return subprocess.CompletedProcess(cmd, json_rc, json_payload or "", "")
        if "/Get-WimInfo" in joined:
            if not dism_ok:
                return subprocess.CompletedProcess(cmd, 1, "", "boom")
            if "/Index:1" in joined:
                return subprocess.CompletedProcess(cmd, 0, DISM_DETAIL, "")
            return subprocess.CompletedProcess(cmd, 0, DISM_LIST, "")
        return subprocess.CompletedProcess(cmd, 1, "", "unexpected")
    return _run


def image(name, version="10.0.19043.1052", arch=9, lang=None, langs=("es-ES",)):
    return {
        "ImageName": name,
        "Version": version,
        "Architecture": arch,
        "Language": lang,
        "Languages": list(langs),
        "DefaultLanguageIndex": 0,
    }


failures = []


def check(label, meta, **expected):
    got = {k: getattr(meta, k) for k in expected}
    ok = got == expected
    print(("OK   " if ok else "FAIL ") + f"{label}: {got}")
    if not ok:
        failures.append(f"{label}: {got} != {expected}")


# --- 1. PowerShell responde bien (arquitectura como enum, Language null)
iso_inspector.run = make_run(json.dumps([
    image("Windows 10 Pro"),
    image("Windows 10 Home"),
]))
check("PS completo", iso_inspector.inspect(str(FAKE)),
      version="10.0.19043.1052", arch="x64", lang="es-ES", build="19043",
      editions=["Windows 10 Pro", "Windows 10 Home"])

# --- 2. PowerShell devuelve nulls -> fallback DISM
iso_inspector.run = make_run(json.dumps({"ImageName": "Windows 10 Pro",
                                         "Version": None, "Architecture": None}))
check("PS con nulls -> DISM", iso_inspector.inspect(str(FAKE)),
      version="10.0.19043.1052", arch="x64", lang="es-ES", build="19043",
      editions=["Windows 10 Pro", "Windows 10 Home"])

# --- 3. PowerShell falla (código != 0) -> fallback DISM
iso_inspector.run = make_run("", json_rc=1)
check("PS falla -> DISM", iso_inspector.inspect(str(FAKE)),
      version="10.0.19043.1052", arch="x64", lang="es-ES",
      editions=["Windows 10 Pro", "Windows 10 Home"])

# --- 4. JSON sin ediciones -> se completan por DISM sin perder lo leído
iso_inspector.run = make_run(json.dumps({"Version": "10.0.19043.1052",
                                         "Architecture": 9,
                                         "Languages": ["es-ES"],
                                         "DefaultLanguageIndex": 0}))
check("PS sin ImageName", iso_inspector.inspect(str(FAKE)),
      version="10.0.19043.1052", arch="x64", lang="es-ES",
      editions=["Windows 10 Pro", "Windows 10 Home"])

# --- 5. Nada legible (sin ISO válida)
iso_inspector.run = make_run("", json_rc=1, dism_ok=False)
check("todo falla", iso_inspector.inspect(str(FAKE)), version="unknown", arch="unknown")

# --- 6. Validación de build: ISO 19043 sobre sistema 17133 -> OK
meta = iso_inspector.ISOMetadata(version="10.0.19043.1052", build="19043",
                                 arch="x64", lang="es-ES",
                                 editions=["Windows 10 Pro"])
validators.inspect_iso = lambda drive: meta


def current(build_value):
    return {"version": "10.0", "build": build_value, "edition": "Professional",
            "arch": "AMD64", "lang": "es-ES", "install_date": "unknown"}


validators.get_current_version = lambda: current("17133")
errs = validators.validate_iso("F:\\", "upgrade")
print(("OK   " if not errs else "FAIL ") + f"sistema 17133 vs ISO 19043: {errs or 'sin errores'}")
if errs:
    failures.append(f"validacion 17133: {errs}")

validators.get_current_version = lambda: current("22631")
errs = validators.validate_iso("F:\\", "upgrade")
print(("OK   " if errs else "FAIL ") + f"sistema 22631 vs ISO 19043: {errs}")
if not errs:
    failures.append("validacion 22631: debió rechazar la ISO más antigua")

shutil.rmtree(FAKE, ignore_errors=True)
print("\nFAILS:", failures or "ninguno")
sys.exit(1 if failures else 0)
