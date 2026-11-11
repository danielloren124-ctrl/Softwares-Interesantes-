# Windows ISO Version Manager

Aplicación de escritorio (Tkinter, x64) para **actualizar (upgrade) o
disminuir (downgrade)** una instalación de Windows 10/11 usando una ISO
local.

> ⚠ **Downgrade no soportado oficialmente por Microsoft.** El modo
> "Avanzado" puede fallar y dejar el sistema inestable. Úselo bajo su
> responsabilidad.

## Requisitos

- Windows 10/11 x64.
- Python 3.11+ x64.
- Ejecutar **como administrador** (la app se auto-eleva).

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución en desarrollo

```powershell
python main.py
```

## Empaquetado

```powershell
cd build
pyinstaller build.spec
```

El ejecutable resultante está en `build/dist/WindowsISOManager.exe`
(solicita elevación vía `--uac-admin`).

### Compilación sin acceso directo a PyPI

La red corporativa sólo permite salir por el proxy `172.20.1.12:3128`, y
`pip install` se queda colgado al descargar los wheels. Para reproducir el
entorno ya preparado en este repositorio:

```powershell
python -m venv .venv
python build\fetch_wheels.py         # baja los wheels a temp/wheelhouse
.\.venv\Scripts\python.exe -m pip install --no-index --find-links temp\wheelhouse `
    pyinstaller psutil pywin32 wmi requests packaging
cd build
..\.venv\Scripts\pyinstaller.exe --noconfirm --clean --workpath work --distpath dist build.spec
```

El `.exe` es *one-file*: en tiempo de ejecución se descomprime en un
directorio temporal, pero `config.py` detecta el modo congelado
(`sys.frozen`) y crea `logs/` y `temp/` **junto al ejecutable**, no dentro
de esa carpeta temporal.

## Pruebas

Chequeos offline (no requieren ISO ni permisos de administrador); simulan
las respuestas de PowerShell y de `dism.exe`, incluida la salida en español:

```powershell
python tests\test_inspector.py
```

## Flujo de uso

1. Pestaña **Inicio** → Seleccionar ISO y *Analizar compatibilidad*.
2. Pestaña **Ejecución** → *Iniciar proceso* (upgrade).
3. Pestaña **Downgrade** → Elegir modo A/B/C. El modo B exige escribir
   literalmente `DOWNGRADE`.
4. Pestaña **Logs** → Ver `logs/*.log`.

## Limitaciones conocidas

- El downgrade in-place está bloqueado por el instalador de Microsoft.
  El modo B intenta sortear los avisos mediante `setupconfig.ini`
  (`Compat IgnoreWarning=On`, `Migrate IgnoreWarning=On`), pero puede
  fallar en Windows 11 → Windows 10 por diseño de Microsoft.
- El modo A (seguro) requiere intervención manual al final del OOBE.
- No se descargan ISOs: debe aportar una ISO oficial de Microsoft.

## Logs

- `logs/app.log` — log rotativo global.
- `logs/upgrade.log` — salida de `setup.exe` en upgrade.
- `logs/downgrade_safe.log`, `logs/downgrade_advanced.log`.

## Licencia

Uso personal. Respete la EULA de Microsoft al manipular imágenes ISO.
