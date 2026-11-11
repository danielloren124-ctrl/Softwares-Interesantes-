"""Main Tkinter window with tabbed workflow."""
import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from config import APP_NAME, APP_VERSION, LOG_DIR
from core.downgrade_engine import mode_advanced, mode_safe
from core.iso_handler import ISOHandler
from core.iso_inspector import inspect as inspect_iso
from core.upgrade_engine import run_upgrade
from core.windows_info import (
    free_space_gb,
    get_current_version,
    on_ac_power,
)
from ui.widgets import Semaphore
from utils import validators
from utils.logger import get_logger

logger = get_logger("ui")


class MainWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("920x680")
        try:
            ttk.Style(self).theme_use("clam")
        except tk.TclError:
            pass

        self.iso_path: str | None = None
        self.iso_drive: str | None = None
        self.iso_meta = None
        self.action = tk.StringVar(value="upgrade")
        self.compat_ok = False

        self._build_ui()
        self._load_current_info()

    # --------------------------------------------------------------- UI build
    def _build_ui(self) -> None:
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_home = ttk.Frame(self.nb)
        self.nb.add(self.tab_home, text="Inicio")
        self._build_home()

        self.tab_run = ttk.Frame(self.nb)
        self.nb.add(self.tab_run, text="Ejecución")
        self._build_run()

        self.tab_dg = ttk.Frame(self.nb)
        self.nb.add(self.tab_dg, text="Downgrade")
        self._build_downgrade()

        self.tab_logs = ttk.Frame(self.nb)
        self.nb.add(self.tab_logs, text="Logs")
        self._build_logs()

        self.status = ttk.Label(self, anchor="w", relief="sunken")
        self.status.pack(fill="x", side="bottom")

    def _build_home(self) -> None:
        frm = self.tab_home

        info_frame = ttk.LabelFrame(frm, text="Sistema actual")
        info_frame.pack(fill="x", padx=8, pady=8)
        self.lbl_current = ttk.Label(info_frame, text="Cargando…", justify="left")
        self.lbl_current.pack(anchor="w", padx=8, pady=4)

        iso_frame = ttk.LabelFrame(frm, text="Imagen ISO")
        iso_frame.pack(fill="x", padx=8, pady=8)
        row = ttk.Frame(iso_frame)
        row.pack(fill="x", padx=8, pady=4)
        ttk.Button(row, text="Seleccionar ISO…", command=self._select_iso).pack(side="left")
        self.lbl_iso = ttk.Label(row, text="(ninguna)")
        self.lbl_iso.pack(side="left", padx=8)

        act_frame = ttk.LabelFrame(frm, text="Acción")
        act_frame.pack(fill="x", padx=8, pady=8)
        ttk.Radiobutton(act_frame, text="Upgrade (actualizar)",
                        variable=self.action, value="upgrade").pack(anchor="w", padx=8)
        ttk.Radiobutton(act_frame, text="Downgrade (disminuir)",
                        variable=self.action, value="downgrade").pack(anchor="w", padx=8)

        self.btn_analyze = ttk.Button(
            frm, text="Analizar compatibilidad", command=self._analyze
        )
        self.btn_analyze.pack(pady=8)

        self.semaforo = Semaphore(frm)
        self.semaforo.pack()
        self.lbl_compat = ttk.Label(frm, text="", justify="left")
        self.lbl_compat.pack(padx=8, pady=4, anchor="w")

    def _build_run(self) -> None:
        frm = self.tab_run
        row = ttk.Frame(frm)
        row.pack(fill="x", padx=8, pady=8)
        self.btn_start = ttk.Button(
            row, text="Iniciar proceso", command=self._start_run, state="disabled"
        )
        self.btn_start.pack(side="left")
        self.btn_cancel = ttk.Button(
            row, text="Cancelar", command=self._cancel_run, state="disabled"
        )
        self.btn_cancel.pack(side="left", padx=8)

        self.progress = ttk.Progressbar(frm, mode="indeterminate")
        self.progress.pack(fill="x", padx=8, pady=4)

        self.log_text = tk.Text(frm, wrap="word", height=20)
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)

    def _build_downgrade(self) -> None:
        frm = self.tab_dg
        banner = tk.Label(
            frm,
            text="⚠ ADVERTENCIA: el downgrade no está soportado oficialmente "
                 "por Microsoft. Puede dejar el sistema inestable y fallar.",
            bg="#c0392b", fg="white", wraplength=820, justify="left",
            padx=8, pady=8,
        )
        banner.pack(fill="x", padx=8, pady=8)

        self.dg_mode = tk.StringVar(value="safe")
        ttk.Radiobutton(frm, text="A. Seguro (respaldo + instalación limpia)",
                        variable=self.dg_mode, value="safe").pack(anchor="w", padx=8)
        ttk.Radiobutton(frm, text="B. Avanzado (bajo responsabilidad del usuario)",
                        variable=self.dg_mode, value="advanced").pack(anchor="w", padx=8)
        ttk.Radiobutton(frm, text="C. Cancelar",
                        variable=self.dg_mode, value="cancel").pack(anchor="w", padx=8)

        row = ttk.Frame(frm)
        row.pack(fill="x", padx=8, pady=4)
        ttk.Label(row, text="Carpeta de respaldo:").pack(side="left")
        self.backup_path = tk.StringVar(
            value=str(Path.home() / "WIManager_Backup")
        )
        ttk.Entry(row, textvariable=self.backup_path, width=50).pack(side="left", padx=4)
        ttk.Button(row, text="…", command=self._pick_backup).pack(side="left")

        self.btn_dg = ttk.Button(
            frm, text="Ejecutar downgrade", command=self._run_downgrade
        )
        self.btn_dg.pack(pady=8)

    def _build_logs(self) -> None:
        frm = self.tab_logs
        row = ttk.Frame(frm)
        row.pack(fill="x", padx=8, pady=4)
        self.log_selector = ttk.Combobox(
            row,
            values=[p.name for p in LOG_DIR.glob("*.log")],
            state="readonly", width=40,
        )
        self.log_selector.pack(side="left")
        self.log_selector.bind(
            "<<ComboboxSelected>>", lambda _e: self._load_log()
        )
        ttk.Button(row, text="Abrir carpeta",
                   command=self._open_log_folder).pack(side="left", padx=4)
        self.log_viewer = tk.Text(frm, wrap="none")
        self.log_viewer.pack(fill="both", expand=True, padx=8, pady=8)

    # --------------------------------------------------------------- helpers
    def _load_current_info(self) -> None:
        info = get_current_version()
        free = free_space_gb("C:\\")
        power = "AC" if on_ac_power() else "batería <40 %"
        self.lbl_current.config(
            text=(
                f"Versión: {info['version']} (build {info['build']})\n"
                f"Edición: {info['edition']}\n"
                f"Arquitectura: {info['arch']}\n"
                f"Idioma: {info['lang']}\n"
                f"Instalado: {info['install_date']}\n"
                f"Espacio libre C: {free:.1f} GB\n"
                f"Energía: {power}"
            )
        )

    def _select_iso(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("ISO", "*.iso")])
        if not path:
            return
        self.iso_path = path
        self.lbl_iso.config(text=path)
        threading.Thread(
            target=self._mount_and_inspect, daemon=True
        ).start()

    def _mount_and_inspect(self) -> None:
        try:
            with ISOHandler(self.iso_path) as drive:  # type: ignore[arg-type]
                self.iso_drive = drive
                meta = inspect_iso(drive)
                self.iso_meta = meta
                self.after(0, lambda: self._update_iso_meta(meta))
        except Exception as exc:
            logger.exception("Mount failed")
            self.after(
                0,
                lambda e=exc: messagebox.showerror(
                    "Error", f"No se pudo montar la ISO: {e}"
                ),
            )

    def _update_iso_meta(self, meta) -> None:
        self.lbl_iso.config(
            text=f"{self.iso_path}  →  {meta.version} | "
                 f"{meta.arch} | {meta.lang} | "
                 f"{', '.join(meta.editions[:3])}"
        )

    def _analyze(self) -> None:
        if not self.iso_path:
            messagebox.showwarning("ISO", "Seleccione una ISO primero.")
            return
        action = self.action.get()
        errors = validators.validate_environment(action)
        try:
            with ISOHandler(self.iso_path) as drive:
                errors += validators.validate_iso(drive, action)
        except Exception as exc:
            errors.append(f"Error montando ISO: {exc}")
        if not errors:
            self.compat_ok = True
            self.semaforo.set_state("ok")
            self.lbl_compat.config(text="✓ Compatible")
            self.btn_start.config(state="normal")
        else:
            self.compat_ok = False
            self.semaforo.set_state("error")
            self.lbl_compat.config(text="✗ " + "\n✗ ".join(errors))
            self.btn_start.config(state="disabled")

    # --------------------------------------------------------------- run tab
    def _start_run(self) -> None:
        if not self.compat_ok:
            return
        if self.action.get() == "downgrade":
            self.nb.select(self.tab_dg)
            return
        self.btn_start.config(state="disabled")
        self.btn_cancel.config(state="normal")
        self.progress.start()
        threading.Thread(target=self._run_upgrade, daemon=True).start()

    def _run_upgrade(self) -> None:
        try:
            with ISOHandler(self.iso_path) as drive:  # type: ignore[arg-type]
                self._append_log(f"Montado en {drive}")
                result = run_upgrade(drive)
                self._append_log(
                    f"Upgrade finalizado: success={result.success} "
                    f"code={result.code} log={result.log_path}"
                )
        except Exception as exc:
            logger.exception("Upgrade failed")
            self._append_log(f"ERROR: {exc}")
        finally:
            self.after(0, self.progress.stop)
            self.after(0, lambda: self.btn_cancel.config(state="disabled"))
            self.after(
                0,
                lambda: self.btn_start.config(
                    state="normal" if self.compat_ok else "disabled"
                ),
            )

    def _cancel_run(self) -> None:
        subprocess.run(
            ["taskkill", "/IM", "setup.exe", "/F"], capture_output=True
        )
        self._append_log("Cancelación solicitada.")

    def _append_log(self, text: str) -> None:
        logger.info(text)
        def _w() -> None:
            self.log_text.insert("end", text + "\n")
            self.log_text.see("end")
        self.after(0, _w)

    # --------------------------------------------------------------- dg tab
    def _pick_backup(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.backup_path.set(path)

    def _run_downgrade(self) -> None:
        mode = self.dg_mode.get()
        if mode == "cancel":
            self.nb.select(self.tab_home)
            return
        if mode == "advanced":
            typed = simpledialog.askstring(
                "Confirmar downgrade avanzado",
                "Escriba DOWNGRADE para confirmar que acepta los riesgos:",
                parent=self,
            )
            if typed != "DOWNGRADE":
                messagebox.showinfo("Cancelado", "Confirmación incorrecta.")
                return
        if not self.iso_path:
            messagebox.showwarning("ISO", "Seleccione una ISO primero.")
            return
        self.btn_dg.config(state="disabled")
        threading.Thread(
            target=self._do_downgrade, args=(mode,), daemon=True
        ).start()

    def _do_downgrade(self, mode: str) -> None:
        try:
            with ISOHandler(self.iso_path) as drive:  # type: ignore[arg-type]
                if mode == "safe":
                    result = mode_safe(drive, self.backup_path.get())
                else:
                    result = mode_advanced(drive)
                self._append_log(
                    f"Downgrade {mode}: success={result.success} "
                    f"code={result.code}"
                )
        except Exception as exc:
            logger.exception("Downgrade failed")
            self._append_log(f"ERROR: {exc}")
        finally:
            self.after(0, lambda: self.btn_dg.config(state="normal"))

    # --------------------------------------------------------------- logs tab
    def _load_log(self) -> None:
        name = self.log_selector.get()
        if not name:
            return
        path = LOG_DIR / name
        try:
            self.log_viewer.delete("1.0", "end")
            self.log_viewer.insert(
                "1.0", path.read_text(encoding="utf-8", errors="replace")
            )
        except Exception as exc:
            messagebox.showerror("Log", str(exc))

    def _open_log_folder(self) -> None:
        os.startfile(str(LOG_DIR))
