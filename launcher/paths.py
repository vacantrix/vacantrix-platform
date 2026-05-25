"""Централизованное определение пути к resources/ — работает в dev и в frozen EXE."""

import sys
from pathlib import Path


def _find_resources() -> Path:
    """
    Ищет папку resources/ в трёх местах по приоритету:
    1. PyInstaller _MEIPASS  (one-file EXE)
    2. Папка рядом с EXE    (портативный запуск)
    3. Корень проекта       (запуск из исходников)
    """
    if getattr(sys, "frozen", False):
        # В frozen-режиме __file__ ненадёжен — используем _MEIPASS
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        if (meipass / "resources").exists():
            return meipass / "resources"
        # Fallback: resources/ рядом с .exe
        exe_dir = Path(sys.executable).parent
        if (exe_dir / "resources").exists():
            return exe_dir / "resources"

    # Dev: launcher/paths.py → parent = launcher/ → parent = project_root/
    return Path(__file__).resolve().parent.parent / "resources"


RESOURCES: Path = _find_resources()
