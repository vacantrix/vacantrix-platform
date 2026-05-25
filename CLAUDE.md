# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Структура проекта

```
vacantrix-platform/
├── launcher/               ← PySide6 GUI-платформа (магазин + лаунчер инструментов)
│   ├── app.py              (MainWindow — главное окно)
│   ├── paths.py            (RESOURCES — путь к ресурсам, работает в dev и EXE)
│   ├── theme.py            (стили PySide6, красная палитра)
│   ├── core/
│   │   ├── auth_manager.py (AuthManager — сессия email/password через Supabase)
│   │   ├── supabase_api.py (все REST-запросы к Supabase)
│   │   ├── downloader.py   (DownloadWorker, needs_update, launch)
│   │   ├── cache.py        (дисковый кэш API-ответов)
│   │   ├── config.py       (SUPABASE_URL, ANON ключ, APP_VERSION)
│   │   ├── vx_profile.py   (get/upsert vx_profiles — кросс-проектный профиль)
│   │   └── yookassa_api.py (YooKassa платежи)
│   ├── screens/
│   │   ├── auth_screen.py       (экран входа/регистрации)
│   │   ├── catalog_screen.py    (каталог инструментов)
│   │   ├── cabinet_screen.py    (личный кабинет, подписки, display_name)
│   │   └── tool_detail_screen.py (карточка инструмента)
│   └── widgets/
│       ├── tool_card.py         (карточка в каталоге)
│       ├── image_carousel.py    (карусель скриншотов)
│       ├── payment_modal.py     (модалка оплаты)
│       ├── download_dialog.py   (диалог скачивания EXE)
│       └── toast.py             (всплывающие уведомления)
│
├── resources/              ← UI-ресурсы (иконки, GIF-фон, конфиг)
│   ├── avito_icon.png      ← иконка Авито-бота для каталога (код бота в vacantrix-avito/)
│   └── screenshots/avito/  ← скриншоты Авито-бота для каталога
├── data/                   ← Runtime-данные (session.json)
├── logs/                   ← Логи запусков
├── packaging/              ← PyInstaller spec
├── main.py                 (точка входа)
├── build.py                (сборка EXE через PyInstaller)
└── release.py              (публикация релиза платформы на GitHub)
```

> ⚠️ Код Авито-бота (`vacantrix/avito/`) **перенесён** в отдельный репозиторий `vacantrix-avito/`
> (май 2026). В этом репо от него остались только ресурсы (иконка, скриншоты) для каталога.

## Запуск

```bash
# GUI-лаунчер (платформа)
python main.py

# Dev-режим (отключена проверка подписки — если поддерживается)
# python main.py --dev
```

## Сборка и релиз

```bash
# Собрать EXE платформы
python build.py

# Собрать EXE + создать GitHub Release
python release.py
python release.py --version 1.1.0     # явно задать версию
python release.py --skip-build        # только опубликовать готовый dist/
```

Текущий актуальный релиз: **`v1.0.0`** (`VacantrixLauncher.exe`, 255 МБ).

> В репо также присутствует тег `avito-v1.0.0` — это устаревший релиз Авито-бота,
> опубликованный до разделения. Его нужно удалить, чтобы `/releases/latest/` снова
> указывал на платформу.

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

`SUPABASE_URL` и `SUPABASE_ANON` также прописаны в `launcher/core/config.py`.

## Архитектура

`MainWindow` (`launcher/app.py`) — PySide6-окно. Навигация через `QStackedWidget`:

| Индекс | Экран | Класс |
|--------|-------|-------|
| 0 | Вход / регистрация | `AuthScreen` |
| 1 | Каталог инструментов | `CatalogScreen` |
| 2 | Личный кабинет | `CabinetScreen` |
| 3 | Карточка инструмента | `ToolDetailScreen` |

**Сессия**: `AuthManager` хранит токены в `data/session.json`. При запуске восстанавливает
сессию через `refresh_token`. Истёкший токен обновляется автоматически.

**Профиль (`vx_profile.py`)**: при входе вызывается `upsert_platform_profile_async()` —
синхронизирует `display_name` с таблицей `vx_profiles` (кросс-проектный профиль).
При сохранении ника в кабинете вызывается `set_display_name_async()`.

**Инструменты**: хранятся в `~/AppData/Local/VacantrixPlatform/tools/<slug>/<Name>.exe`.
`DownloadWorker` (QThread) скачивает EXE с прогресс-баром.
`needs_update()` сравнивает `version.txt` с версией из Supabase.

### Supabase (таблицы платформы)

| Таблица | Назначение |
|---------|-----------|
| `tools` | Каталог инструментов (slug, name, version, download_url) |
| `plans` | Тарифные планы (duration_days, price, is_combo) |
| `plan_tools` | Связь планов и инструментов (many-to-many) |
| `subscriptions` | Подписки пользователей (user_id, tool_id, expires_at) |
| `trials` | Счётчик пробных откликов (user_id, tool_id, responses_used) |
| `payments` | История платежей |
| `vx_profiles` | Единый профиль (display_name, hh_applicant_id, avito_user_id) — кросс-проектный |

### Оплата (YooKassa)

`PaymentModal` → `supabase_api.create_payment()` → Edge Function `create-payment` → YooKassa invoice.
После успешной оплаты вызывается `activate_subscription()`.

## Связанные проекты

| Проект | Связь |
|--------|-------|
| `vacantrix-avito` | Авито-бот (отдельный репо), каталог показывает его ресурсы из `resources/` |
| `vacantrix-hh` | HH-бот; распространяется через эту платформу |
| `vacantrix-tasks` | Биржа задач; использует те же `vx_profiles` |
| `vacantrix-web` | Сайт-витрина на GitHub Pages |
