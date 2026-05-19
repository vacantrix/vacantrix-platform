# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / 'resources'), 'resources'),
    ],
    hiddenimports=['keyring.backends.Windows', 'PySide6.QtSvg'],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name='VacantrixLauncher',
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(ROOT / 'resources' / 'icon.ico') if (ROOT / 'resources' / 'icon.ico').exists() else None,
)
