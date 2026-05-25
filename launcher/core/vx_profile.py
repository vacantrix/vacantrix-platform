"""
Синхронизация профиля Платформы с централизованной таблицей vx_profiles.
Ключ связи — web_user_id (UUID из Supabase Auth).
"""
import logging
import threading

from .config import REST_URL, SUPABASE_ANON

log = logging.getLogger(__name__)

_HEADERS_ANON = {
    "apikey": SUPABASE_ANON,
    "Content-Type": "application/json",
}


def _headers(access_token: str) -> dict:
    return {
        "apikey": SUPABASE_ANON,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


# ── Загрузить профиль по web_user_id ──────────────────────────────────────────

def get_profile(access_token: str, web_user_id: str) -> dict | None:
    """Возвращает строку vx_profiles или None."""
    try:
        import requests
        r = requests.get(
            f"{REST_URL}/vx_profiles"
            f"?web_user_id=eq.{web_user_id}"
            f"&select=id,display_name,hh_username,avito_username,subscription_expire",
            headers=_headers(access_token),
            timeout=8,
        )
        if r.ok:
            rows = r.json()
            return rows[0] if rows else None
    except Exception as e:
        log.warning("vx_profile.get_profile: %s", e)
    return None


# ── Создать / обновить запись платформы ───────────────────────────────────────

def upsert_platform_profile(access_token: str, web_user_id: str,
                            display_name: str | None = None) -> dict | None:
    """
    Upsert по web_user_id.
    Если запись уже есть — обновляет только переданные поля.
    Возвращает сохранённую строку или None при ошибке.
    """
    try:
        import requests
        payload: dict = {"web_user_id": web_user_id}
        if display_name is not None:
            payload["display_name"] = display_name

        r = requests.post(
            f"{REST_URL}/vx_profiles?on_conflict=web_user_id",
            headers={
                **_headers(access_token),
                "Prefer": "resolution=merge-duplicates,return=representation",
            },
            json=payload,
            timeout=10,
        )
        if r.ok:
            rows = r.json()
            return rows[0] if rows else None
        log.warning("vx_profile.upsert: %s %s", r.status_code, r.text[:200])
    except Exception as e:
        log.warning("vx_profile.upsert_platform_profile: %s", e)
    return None


# ── Обновить только display_name ──────────────────────────────────────────────

def set_display_name(access_token: str, web_user_id: str, display_name: str) -> bool:
    """Обновляет display_name в vx_profiles. Возвращает True при успехе."""
    try:
        import requests
        r = requests.patch(
            f"{REST_URL}/vx_profiles?web_user_id=eq.{web_user_id}",
            headers={
                **_headers(access_token),
                "Prefer": "return=minimal",
            },
            json={"display_name": display_name},
            timeout=8,
        )
        return r.ok
    except Exception as e:
        log.warning("vx_profile.set_display_name: %s", e)
    return False


# ── Async-обёртки (не блокируют Qt UI) ───────────────────────────────────────

def upsert_platform_profile_async(access_token: str, web_user_id: str,
                                  display_name: str | None = None,
                                  callback=None) -> None:
    """Запускает upsert в фоновом потоке. callback(profile | None) вызывается в том же потоке."""
    def _run():
        result = upsert_platform_profile(access_token, web_user_id, display_name)
        if callback:
            try:
                callback(result)
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()


def set_display_name_async(access_token: str, web_user_id: str,
                           display_name: str, callback=None) -> None:
    def _run():
        ok = set_display_name(access_token, web_user_id, display_name)
        if callback:
            try:
                callback(ok)
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()
