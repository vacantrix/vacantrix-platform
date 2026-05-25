"""
release.py — Сборка и публикация новой версии Vacantrix Platform

Что делает:
  1. Читает версию из launcher/core/config.py
  2. Собирает VacantrixLauncher.exe через PyInstaller
  3. Создаёт GitHub Release и загружает EXE как ассет
  4. Обновляет ссылку для скачивания на сайте через Supabase

Использование:
    python release.py                    # версия берётся из APP_VERSION в config.py
    python release.py --version 1.2.0   # явно указать версию (обновит config.py)
    python release.py --skip-build      # не пересобирать, только опубликовать
"""

import re
import sys
import shutil
import subprocess
import argparse
from pathlib import Path


def _ensure(package, import_name=None):
    try:
        __import__(import_name or package)
    except ImportError:
        print(f"  Устанавливаю {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package, "-q"])


_ensure("requests")
_ensure("python-dotenv", "dotenv")
_ensure("pyinstaller", "PyInstaller")

import requests
from dotenv import load_dotenv
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent        # vacantrix-platform/
load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / "Vacantrix" / ".env")  # запасной .env из основного проекта

# ── Конфигурация ──────────────────────────────────────────────────────
GITHUB_TOKEN  = os.getenv("GITHUB_TOKEN", "")
GITHUB_OWNER  = "vacantrix"
GITHUB_REPO   = "vacantrix-platform"

SUPABASE_URL  = os.getenv("SUPABASE_URL", "")
SUPABASE_SVC  = os.getenv("SUPABASE_SERVICE_KEY", "")

SPEC          = ROOT / "packaging" / "Launcher.spec"
DIST_EXE      = ROOT / "dist" / "VacantrixLauncher.exe"
CONFIG_PY     = ROOT / "launcher" / "core" / "config.py"

# slug строки в таблице web_apps на сайте
WEB_APP_SLUG  = "vacantrix-platform"

LATEST_DL_URL = (
    f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
    "/releases/latest/download/VacantrixLauncher.exe"
)


# ── Вспомогательные ───────────────────────────────────────────────────

def _gh_headers() -> dict:
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "vacantrix-release",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_SVC,
        "Authorization": f"Bearer {SUPABASE_SVC}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _step(msg: str) -> None:
    print(f"\n{'─'*52}\n  {msg}\n{'─'*52}")


# ── Шаг 1: версия ────────────────────────────────────────────────────

def read_version() -> str:
    text = CONFIG_PY.read_text(encoding="utf-8")
    m = re.search(r'APP_VERSION\s*=\s*["\'](.+?)["\']', text)
    return m.group(1) if m else "1.0.0"


def bump_version(new_version: str) -> None:
    text = CONFIG_PY.read_text(encoding="utf-8")
    updated = re.sub(
        r'(APP_VERSION\s*=\s*["\'])(.+?)(["\'])',
        lambda m: m.group(1) + new_version + m.group(3),
        text,
    )
    CONFIG_PY.write_text(updated, encoding="utf-8")
    print(f"  APP_VERSION обновлён → {new_version}")


# ── Шаг 2: сборка EXE ────────────────────────────────────────────────

def build() -> None:
    _step("Сборка EXE (PyInstaller)")
    for d in (ROOT / "dist", ROOT / "build"):
        if d.exists():
            shutil.rmtree(d)
            print(f"  Очищено: {d.name}/")

    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(SPEC), "--noconfirm",
         "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build")],
        cwd=ROOT,
    )
    if result.returncode != 0:
        print("❌ Сборка завершилась с ошибкой.")
        sys.exit(1)

    if not DIST_EXE.exists():
        print(f"❌ EXE не найден: {DIST_EXE}")
        sys.exit(1)

    size_mb = DIST_EXE.stat().st_size / 1024 / 1024
    print(f"✅ Готово: {DIST_EXE.name}  ({size_mb:.1f} МБ)")


# ── Шаг 3: GitHub Release ─────────────────────────────────────────────

def get_or_create_release(version: str) -> tuple[int, str]:
    _step(f"GitHub Release v{version}")

    tag = f"v{version}"
    r = requests.get(
        f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/tags/{tag}",
        headers=_gh_headers(), timeout=60,
    )

    if r.status_code == 200:
        data = r.json()
        print(f"  Релиз уже существует, обновляем ассеты.")
        return data["id"], data["upload_url"].split("{")[0]

    r = requests.post(
        f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases",
        headers=_gh_headers(),
        json={
            "tag_name":   tag,
            "name":       f"Vacantrix Platform {tag}",
            "body":       f"## Vacantrix Platform {tag}\n\nАвтоматическая сборка.",
            "draft":      False,
            "prerelease": False,
        },
        timeout=60,
    )
    if r.status_code not in (200, 201):
        print(f"❌ Ошибка создания релиза: {r.status_code} {r.text[:200]}")
        sys.exit(1)

    data = r.json()
    print(f"✅ Релиз создан: {data['html_url']}")
    return data["id"], data["upload_url"].split("{")[0]


def upload_exe(release_id: int, upload_url: str) -> None:
    print("  Загрузка VacantrixLauncher.exe...")

    r = requests.get(
        f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/{release_id}/assets",
        headers=_gh_headers(), timeout=15,
    )
    for asset in (r.json() if r.ok else []):
        if asset["name"] == "VacantrixLauncher.exe":
            requests.delete(
                f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/assets/{asset['id']}",
                headers=_gh_headers(), timeout=15,
            )
            print("  Старый ассет удалён.")

    size_mb = DIST_EXE.stat().st_size / 1024 / 1024
    print(f"  Размер файла: {size_mb:.1f} МБ")

    for attempt in range(3):
        print(f"  Попытка {attempt + 1}/3...")
        try:
            with open(DIST_EXE, "rb") as f:
                r = requests.post(
                    f"{upload_url}?name=VacantrixLauncher.exe",
                    headers={**_gh_headers(), "Content-Type": "application/octet-stream"},
                    data=f,
                    timeout=600,
                )
            if r.status_code in (200, 201):
                url = r.json().get("browser_download_url", "")
                print(f"✅ Загружено: {url}")
                return
            print(f"  Ошибка {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"  Исключение: {e}")

    print("❌ Не удалось загрузить ассет после 3 попыток.")
    sys.exit(1)


# ── Шаг 4: обновление сайта ───────────────────────────────────────────

def update_website(version: str) -> None:
    _step("Обновление ссылки на сайте (Supabase web_apps)")

    if not SUPABASE_URL or not SUPABASE_SVC:
        print("⚠️  SUPABASE_URL или SUPABASE_SERVICE_KEY не заданы — пропускаем.")
        return

    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/web_apps?slug=eq.{WEB_APP_SLUG}",
        headers=_sb_headers(),
        json={"download_url": LATEST_DL_URL},
        timeout=10,
    )
    if r.status_code in (200, 204):
        print(f"✅ Сайт обновлён → {LATEST_DL_URL}")
    else:
        print(f"⚠️  Не удалось обновить сайт: {r.status_code} {r.text[:100]}")
        print(f"   Убедитесь, что в таблице web_apps есть строка с slug='{WEB_APP_SLUG}'")


# ── Точка входа ───────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Сборка и публикация Vacantrix Platform")
    parser.add_argument("--version",    help="Явно задать версию (например 1.2.0)")
    parser.add_argument("--skip-build", action="store_true", help="Не пересобирать EXE")
    args = parser.parse_args()

    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN не задан в .env")
        sys.exit(1)

    version = args.version or read_version()
    if args.version:
        bump_version(version)

    print(f"\n{'='*52}")
    print(f"  Vacantrix Platform v{version} — Релиз")
    print(f"{'='*52}")

    if not args.skip_build:
        build()
    else:
        if not DIST_EXE.exists():
            print(f"❌ --skip-build: EXE не найден в {DIST_EXE}")
            sys.exit(1)
        print(f"  Пропуск сборки. Использую: {DIST_EXE.name}")

    release_id, upload_url = get_or_create_release(version)
    upload_exe(release_id, upload_url)
    update_website(version)

    print(f"\n{'='*52}")
    print(f"  Всё готово!")
    print(f"  Релиз : https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest")
    print(f"  Сайт  : https://vacantrix.github.io/vacantrix-web/")
    print(f"{'='*52}\n")


if __name__ == "__main__":
    main()
