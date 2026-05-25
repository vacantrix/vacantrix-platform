# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Структура проекта

```
vacantrix-platform/
├── launcher/               ← PySide6 GUI-платформа (магазин + лаунчер инструментов)
│   ├── app.py              (MainWindow — главное окно)
│   ├── paths.py            (RESOURCES — путь к ресурсам, работает в dev и EXE)
│   ├── theme.py            (стили PySide6)
│   ├── core/
│   │   ├── auth_manager.py (AuthManager — сессия email/password через Supabase)
│   │   ├── supabase_api.py (все REST-запросы к Supabase)
│   │   ├── downloader.py   (DownloadWorker, needs_update, launch)
│   │   ├── cache.py        (дисковый кэш API-ответов)
│   │   ├── config.py       (SUPABASE_URL, ANON ключ, APP_VERSION)
│   │   └── yookassa_api.py (YooKassa платежи)
│   ├── screens/
│   │   ├── auth_screen.py       (экран входа/регистрации)
│   │   ├── catalog_screen.py    (каталог инструментов)
│   │   ├── cabinet_screen.py    (личный кабинет, подписки)
│   │   └── tool_detail_screen.py (карточка инструмента)
│   └── widgets/
│       ├── tool_card.py         (карточка в каталоге)
│       ├── image_carousel.py    (карусель скриншотов)
│       ├── payment_modal.py     (модалка оплаты)
│       ├── download_dialog.py   (диалог скачивания EXE)
│       └── toast.py             (всплывающие уведомления)
│
├── vacantrix/              ← Ядро автоматизации (Avito-бот)
│   ├── avito/
│   │   ├── bot.py          (AvitoApplyBot — главный класс)
│   │   ├── driver.py       (DriverManager, InterruptedError, AuthLostError)
│   │   ├── parser.py       (VacancyParser, ProgressTracker)
│   │   ├── applier.py      (ApplyHandler)
│   │   ├── auth.py         (ensure_authenticated, save/load cookies)
│   │   └── workers.py      (QThread-воркеры для GUI)
│   └── core/
│       └── config.py       (AvitoConfig dataclass, load_config)
│
├── resources/              ← UI-ресурсы (иконки, GIF-фон, конфиг)
├── data/                   ← Runtime-данные (session.json, cookies)
├── logs/                   ← Логи запусков
├── packaging/              ← PyInstaller spec
├── main.py                 (CLI-точка входа)
├── avito_main.py           (CLI-запуск Avito-бота)
├── run_app.pyw             (GUI-запуск без консоли, Windows)
├── build.py                (сборка EXE через PyInstaller)
├── release.py              (публикация релиза платформы)
└── release_avito.py        (публикация релиза Avito-бота)
```

## Запуск

```bash
# GUI-лаунчер (платформа)
python run_app.pyw

# CLI-режим (без GUI)
python main.py

# Avito-бот напрямую (CLI)
python avito_main.py --config resources/config.yaml

# Dev-запуск с отключённой проверкой подписки
python main.py --dev
```

## Сборка и релиз

```bash
# Собрать EXE платформы
python build.py

# Собрать EXE + создать GitHub Release + обновить ссылку на сайте
python release.py
python release.py --version 1.1.0     # явно задать версию
python release.py --skip-build        # только опубликовать готовый dist/

# Релиз Avito-бота отдельно
python release_avito.py
```

`APP_VERSION` читается из `launcher/core/config.py`.

## Переменные окружения

`.env` в корне проекта:

```
SUPABASE_URL=           # URL проекта Supabase
SUPABASE_ANON=          # Anon/publishable ключ
SUPABASE_SERVICE_KEY=   # Service_role ключ (для release.py)
GITHUB_TOKEN=           # GitHub PAT с доступом repo
YOOKASSA_SHOP_ID=       # ID магазина YooKassa
YOOKASSA_SECRET_KEY=    # Секретный ключ YooKassa
```

`SUPABASE_URL` и `SUPABASE_ANON` также прописаны прямо в `launcher/core/config.py` — тот же Supabase-проект, что и у `vacantrix-hh` (`fgcffgfyehequucnxegb`).

## Архитектура

### Лаунчер (платформа)

`MainWindow` (`launcher/app.py`) — frameless PySide6-окно с анимированным GIF-фоном. Навигация через `QStackedWidget`:

| Индекс | Экран | Класс |
|--------|-------|-------|
| 0 | Вход / регистрация | `AuthScreen` |
| 1 | Каталог инструментов | `CatalogScreen` |
| 2 | Личный кабинет | `CabinetScreen` |
| 3 | Карточка инструмента | `ToolDetailScreen` |

**Сессия**: `AuthManager` хранит токены в `data/session.json`. При запуске пытается восстановить сессию через `refresh_token`. Истёкший токен автоматически обновляется.

**Инструменты**: хранятся на диске в `~/AppData/Local/VacantrixPlatform/tools/<slug>/<Name>.exe`. `DownloadWorker` (QThread) скачивает EXE с прогресс-баром. `needs_update()` сравнивает `version.txt` с версией из Supabase.

**Обновление каталога**: автоматически каждые 15 минут через `QTimer`.

### Avito-бот (`vacantrix/avito/`)

Структура зеркалирует `vacantrix-hh/hh_core/vacantrix/hh/`. Главный цикл в `AvitoApplyBot.run()`:

1. `DriverManager.create_driver()` — Chrome с анти-бот флагами
2. `ensure_authenticated()` — куки → ручной вход
3. `VacancyParser.collect_visible_vacancy_links()` — парсинг ссылок на вакансии
4. `ApplyHandler.apply_to_vacancy()` — отклик на каждую вакансию

`DriverManager.with_reconnect(fn)` — при `WebDriverException` пересоздаёт драйвер (до 2 попыток) и переаутентифицируется.

### Supabase (таблицы)

Тот же проект, что у `vacantrix-hh`. Таблицы платформы:

| Таблица | Назначение |
|---------|-----------|
| `tools` | Каталог инструментов (slug, name, version, download_url) |
| `plans` | Тарифные планы (duration_days, price, is_combo) |
| `plan_tools` | Связь планов и инструментов (many-to-many) |
| `subscriptions` | Подписки пользователей (user_id, tool_id, expires_at) |
| `trials` | Счётчик пробных откликов (user_id, tool_id, responses_used) |
| `payments` | История платежей |

### Оплата (YooKassa)

`PaymentModal` → `supabase_api.create_payment()` → Edge Function `create-payment` → YooKassa invoice. После успешной оплаты вызывается `activate_subscription()`.

## Связанные проекты

| Проект | Связь |
|--------|-------|
| `vacantrix-hh` | Тот же Supabase-проект; HH-бот распространяется через эту платформу |
| `vacantrix-web` | Сайт-витрина на GitHub Pages |
