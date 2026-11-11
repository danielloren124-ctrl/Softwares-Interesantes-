"""Mount / unmount ISO images via PowerShell."""
from pathlib import Path

from utils.logger import get_logger
from utils.shell import run

logger = get_logger("iso_handler")


class ISOHandler:
    """Context manager that mounts an ISO and guarantees unmount."""

    def __init__(self, iso_path: str | Path) -> None:
        self.iso_path = str(Path(iso_path).resolve())
        self.drive: str | None = None

    def __enter__(self) -> str:
        self.drive = self.mount()
        return self.drive

    def __exit__(self, exc_type, exc, tb) -> None:
        self.unmount()

    def mount(self) -> str:
        logger.info("Mounting ISO: %s", self.iso_path)

        # Script mejorado: maneja ISOs ya montadas y espera a que la unidad esté lista
        script = (
            f"$img = Get-DiskImage -ImagePath '{self.iso_path}' -ErrorAction SilentlyContinue; "
            f"if ($img -and $img.Attached) {{ "
            f"  ($img | Get-Volume).DriveLetter "
            f"}} else {{ "
            f"  $mnt = Mount-DiskImage -ImagePath '{self.iso_path}' -PassThru; "
            f"  Start-Sleep -Milliseconds 1000; "
            f"  ($mnt | Get-Volume).DriveLetter "
            f"}}"
        )

        result = run(["powershell", "-NoProfile", "-Command", script])
        letter = (result.stdout or "").strip()

        if not letter:
            raise RuntimeError(f"Failed to mount ISO: {self.iso_path}")

        # FIX CRÍTICO: Agregar '\\' para que Path() apunte a la raíz (Ej: "E:\\")
        drive = f"{letter[0]}:\\"
        logger.info("ISO mounted at %s", drive)
        return drive

    def unmount(self) -> None:
        if not self.iso_path:
            return
        logger.info("Unmounting ISO: %s", self.iso_path)
        try:
            run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Dismount-DiskImage -ImagePath '{self.iso_path}' "
                    f"-ErrorAction SilentlyContinue",
                ]
            )
        except Exception as exc:
            logger.error("Unmount failed: %s", exc)
