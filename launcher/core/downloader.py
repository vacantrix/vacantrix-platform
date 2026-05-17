import subprocess
from pathlib import Path

import requests
from PySide6.QtCore import QThread, Signal

TOOLS_DIR = Path(__file__).parent.parent.parent / "tools"


def get_local_version(slug: str) -> str | None:
    ver_file = TOOLS_DIR / slug / "version.txt"
    return ver_file.read_text().strip() if ver_file.exists() else None


def is_downloaded(slug: str, name: str) -> bool:
    """Возвращает True если EXE уже скачан локально."""
    return (TOOLS_DIR / slug / f"{name}.exe").exists()


def needs_update(slug: str, remote_version: str) -> bool:
    """True если локальная версия отсутствует или не совпадает с remote_version."""
    return get_local_version(slug) != remote_version


def launch(slug: str, name: str) -> bool:
    exe = TOOLS_DIR / slug / f"{name}.exe"
    if not exe.exists():
        return False
    subprocess.Popen([str(exe)])
    return True


class DownloadWorker(QThread):
    progress  = Signal(int, int)   # bytes_done, total
    finished  = Signal()
    error     = Signal(str)

    def __init__(self, slug: str, download_url: str, version: str, exe_name: str):
        super().__init__()
        self._slug         = slug
        self._download_url = download_url
        self._version      = version
        self._exe_name     = exe_name
        self._cancelled    = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self):
        self._cancelled = False
        dest_dir = TOOLS_DIR / self._slug
        dest_dir.mkdir(parents=True, exist_ok=True)
        exe_path = dest_dir / f"{self._exe_name}.exe"

        try:
            r = requests.get(self._download_url, stream=True, timeout=60)
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            done  = 0
            with open(exe_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if self._cancelled:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    self.progress.emit(done, total)

            if self._cancelled:
                try:
                    exe_path.unlink(missing_ok=True)
                except Exception:
                    pass
                return

            (dest_dir / "version.txt").write_text(self._version)
            self.finished.emit()
        except Exception as e:
            try:
                exe_path.unlink(missing_ok=True)
            except Exception:
                pass
            if not self._cancelled:
                self.error.emit(str(e))
