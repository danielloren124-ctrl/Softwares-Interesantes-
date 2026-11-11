# agent.md — Guía para agentes de IA

Documento de contexto para asistentes/agentes que trabajen en este
repositorio. Describe qué es el proyecto, cómo está organizado, qué
invariantes se deben respetar y cómo verificar los cambios.

## 1. Qué es este proyecto

Aplicación de escritorio **Windows-only** escrita en Python + Tkinter que
automatiza:

| Flujo | Descripción | Módulo |
|---|---|---|
| **Upgrade** | Actualización in-place de Windows 10/11 desde una ISO local montada. | `core/upgrade_engine.py` |
| **Downgrade A (seguro)** | Respaldo del perfil de usuario + instalación limpia. | `core/downgrade_engine.py` (`mode_safe`) |
| **Downgrade B (avanzado)** | Extrae la ISO, parchea `setupconfig.ini` y fuerza `ignorewarning`. No soportado por Microsoft. | `core/downgrade_engine.py` (`mode_advanced`) |

No descarga ISOs: el usuario aporta una ISO oficial de Microsoft.

## 2. Estructura

```text
windows_iso_manager/
├── agent.md                  # este archivo
├── README.md                 # documentación de usuario
├── requirements.txt
├── main.py                   # entry point (auto-elevación + MainWindow)
├── config.py                 # constantes y rutas (BASE_DIR, LOG_DIR, TEMP_DIR)
├── core/
│   ├── admin.py              # is_admin / ensure_admin (ShellExecuteW runas)
│   ├── windows_info.py       # versión, build, edición, arq., idioma, disco, batería
│   ├── iso_handler.py        # ISOHandler (context manager mount/unmount)
│   ├── iso_inspector.py      # lectura de install.wim/esd vía DISM
│   ├── upgrade_engine.py     # setup.exe /auto upgrade
│   ├── downgrade_engine.py   # modos safe y advanced
│   └── backup.py             # robocopy del perfil + pnputil export
├── ui/
│   ├── main_window.py        # ventana principal con 4 pestañas
│   ├── widgets.py            # Semaphore (semáforo verde/rojo)
│   └── dialogs.py            # confirmación por texto
├── utils/
│   ├── logger.py             # logger rotativo a logs/app.log
│   ├── shell.py              # subprocess wrapper (CREATE_NO_WINDOW)
│   └── validators.py         # validaciones de entorno e ISO
├── tests/
│   └── test_inspector.py     # pruebas offline del inspector y validadores
├── logs/                     # runtime (ignorado por git)
├── temp/                     # runtime (ignorado por git)
└── build/
    ├── build.spec            # PyInstaller (uac_admin=True)
    └── fetch_wheels.py       # descarga offline de wheels vía proxy
```

## 3. Invariantes (no romper)

1. **Toda operación sobre una ISO pasa por `ISOHandler`** como context
   manager: garantiza `Dismount-DiskImage` incluso si `setup.exe` falla.
2. **La elevación es obligatoria.** `main.py` llama `admin.ensure_admin()`
   antes de crear la UI; sin admin `dism`, `pnputil` y `setup.exe` fallan.
3. **Ningún proceso bloqueante se ejecuta en el hilo de Tk.** Upgrade y
   downgrade corren en `threading.Thread(daemon=True)`; la UI se actualiza
   sólo vía `self.after(0, ...)`.
4. **Todo lo que se ejecuta queda en un log** dentro de `config.LOG_DIR`.
   El módulo `utils.shell.run` centraliza subprocess y logging.
5. **El downgrade avanzado exige confirmación literal `DOWNGRADE`** antes
   de tocar nada. No eliminar esa barrera.
6. **Rutas siempre con `pathlib.Path`**, nunca concatenación de strings.
7. **Type hints en funciones públicas**; el código debe pasar
   `python -m compileall .` sin errores.

## 4. Convenciones

- Idioma del código (identificadores, docstrings): inglés.
- Idioma de la UI y mensajes al usuario: español.
- Un módulo por responsabilidad; `core/` no importa `ui/`.
- `config.py` sólo contiene constantes y creación de directorios.
- Resultados de procesos largos: dataclass `Result` con
  `(success, code, log_path, message)`.
- Excepciones amplias sólo en los límites (UI, hilos), siempre logueadas
  con `logger.exception`.

## 5. Verificación tras un cambio

```powershell
python -m compileall -q .     # sintaxis
python main.py                # smoke test manual (requiere admin)
```

Checklist funcional:

- [ ] `python -m compileall .` sin errores.
- [ ] La app se eleva sola si se lanza sin admin.
- [ ] Seleccionar ISO → se muestra versión/arq./idioma/ediciones.
- [ ] *Analizar compatibilidad* pinta el semáforo en verde o lista errores.
- [ ] Upgrade escribe `logs/upgrade.log` y la ISO se desmonta al terminar.
- [ ] Downgrade B rechaza cualquier texto distinto de `DOWNGRADE`.
- [ ] Pestaña Logs lista y muestra todos los `.log`.
- [ ] `cd build; pyinstaller build.spec` genera un exe que pide UAC.

## 6. Trampas conocidas

- **Cadena de lectura de la ISO**: `Get-WindowsImage` → validar que llegaron
  `Version` y `Architecture` → si no, `_fallback_dism()`. `_fallback_dism`
  sólo rellena los campos que sigan en `unknown`, por eso se puede invocar
  también como última pasada para completar `editions` sin pisar lo leído.
- **Comparación de versiones**: usar el **build** (`19043`), no
  `Major.Minor` — Windows 10 y 11 ambos reportan `10.0`, así que comparar
  `10.0` no distingue nada. `validators._build_number()` hace esa extracción.
- **Unidad montada sin barra**: `Path("E:")` es la *unidad relativa* (directorio
  actual de E:), no su raíz. Toda ruta de unidad debe construirse como
  `f"{letra}:\\"`; de lo contrario aparece `E:sources\install.wim` y `dism`
  busca el archivo relativo al CWD del proceso. Por eso `ISOHandler.mount()`
  devuelve `"E:\\"`.
- **Localización de DISM**: `dism.exe` responde en el idioma del sistema
  (`Índice`, `Nombre`, `Versión`, `Arquitectura`). No parsear texto de DISM
  como fuente principal: `Get-WindowsImage | ConvertTo-Json` da claves fijas
  en inglés. El parser de texto sólo es un *fallback* y acepta ambos idiomas.
- **Codificación de consola**: las herramientas nativas escriben en la página
  de códigos OEM (cp850 en español). Usar `utils.shell.oem_encoding()` al
  decodificar su salida; con la ANSI por defecto se rompen los acentos y los
  regex de `Índice`/`Versión` dejan de coincidir.
- **`ConvertTo-Json` y enums**: un enum de PowerShell se serializa como
  número (`Architecture: 9` = x64), no como `"x64"`. Normalizar siempre con
  `_norm_arch()` antes de validar la arquitectura.
- **ESD comprimido**: `dism /Get-WimInfo` funciona también sobre
  `install.esd`, pero es más lento; no asumir que siempre es `.wim`.
- **Idioma**: el ISO puede reportar `en-US` y el sistema `es-ES`; la
  validación compara sólo los dos primeros caracteres.
- **Downgrade real 11 → 10**: Microsoft lo bloquea por diseño. El modo B
  sólo suprime advertencias; no garantizar éxito en la UI ni en docs.
- **Robocopy**: códigos de salida `< 8` se consideran éxito. No cambiar a
  `== 0`.
- **PyInstaller `uac_admin=True`**: el exe pide elevación; en desarrollo
  la elevación la hace `core/admin.py`.

## 7. Fuera de alcance

- Descarga o verificación de integridad de ISOs.
- Activación de licencias.
- Soporte para arquitecturas ARM64/x86.
- Creación de particiones o instalación dual-boot.
