"""Собирает VacantrixLauncher.exe в папку dist/"""
import subprocess, sys, shutil
from pathlib import Path

ROOT = Path(__file__).parent
SPEC = ROOT / "packaging" / "Launcher.spec"
DIST = ROOT / "dist"


def main():
    if DIST.exists():
        shutil.rmtree(DIST)

    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(SPEC), "--distpath", str(DIST), "--noconfirm"],
        cwd=ROOT,
    )
    if result.returncode == 0:
        exe = DIST / "VacantrixLauncher.exe"
        print(f"\n✅ Готово: {exe}")
    else:
        print("\n❌ Сборка провалилась")
        sys.exit(1)


if __name__ == "__main__":
    main()
