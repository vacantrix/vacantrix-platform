import requests
from .config import AUTH_URL, SUPABASE_ANON, REST_URL, FUNCTIONS_URL


def _auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "apikey": SUPABASE_ANON,
        "Content-Type": "application/json",
    }


def _anon_headers() -> dict:
    return {"apikey": SUPABASE_ANON, "Content-Type": "application/json"}


# ── Auth ──────────────────────────────────────────────────────────────────────

def sign_up(email: str, password: str) -> dict:
    r = requests.post(
        f"{AUTH_URL}/signup",
        headers=_anon_headers(),
        json={"email": email, "password": password},
        timeout=15,
    )
    data = r.json()
    if not r.ok:
        raise RuntimeError(data.get("msg") or data.get("message") or "Ошибка регистрации")
    return data


def sign_in(email: str, password: str) -> dict:
    r = requests.post(
        f"{AUTH_URL}/token?grant_type=password",
        headers=_anon_headers(),
        json={"email": email, "password": password},
        timeout=15,
    )
    data = r.json()
    if not r.ok:
        raise RuntimeError(data.get("error_description") or "Неверный email или пароль")
    return data


def refresh_session(refresh_token: str) -> dict:
    r = requests.post(
        f"{AUTH_URL}/token?grant_type=refresh_token",
        headers=_anon_headers(),
        json={"refresh_token": refresh_token},
        timeout=15,
    )
    data = r.json()
    if not r.ok:
        raise RuntimeError("Сессия истекла, войдите снова")
    return data


def get_user(access_token: str) -> dict:
    r = requests.get(
        f"{AUTH_URL}/user",
        headers=_auth_headers(access_token),
        timeout=15,
    )
    if not r.ok:
        raise RuntimeError("Не удалось получить профиль")
    return r.json()


def sign_out(access_token: str) -> None:
    requests.post(
        f"{AUTH_URL}/logout",
        headers=_auth_headers(access_token),
        timeout=10,
    )


# ── Tools & Plans ─────────────────────────────────────────────────────────────

def get_tools() -> list[dict]:
    r = requests.get(
        f"{REST_URL}/tools?select=*&order=sort_order",
        headers=_anon_headers(),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def get_plans(tool_id: str) -> list[dict]:
    r = requests.get(
        f"{REST_URL}/plans?tool_id=eq.{tool_id}&active=eq.true&order=sort_order&select=*",
        headers=_anon_headers(),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def get_combo_plans() -> list[dict]:
    r = requests.get(
        f"{REST_URL}/plans?is_combo=eq.true&active=eq.true&order=sort_order&select=*",
        headers=_anon_headers(),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def get_all_plans() -> list[dict]:
    """Все активные планы одним запросом."""
    r = requests.get(
        f"{REST_URL}/plans?active=eq.true&order=is_combo,sort_order&select=*",
        headers=_anon_headers(),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def get_all_tools() -> list[dict]:
    r = requests.get(
        f"{REST_URL}/tools?select=*&order=sort_order",
        headers=_anon_headers(),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def get_plan_tool_ids(plan_id: str) -> list[str]:
    """Возвращает список tool_id для комбо-плана."""
    r = requests.get(
        f"{REST_URL}/plan_tools?plan_id=eq.{plan_id}&select=tool_id",
        headers=_anon_headers(),
        timeout=15,
    )
    r.raise_for_status()
    return [row["tool_id"] for row in r.json()]


def activate_subscription(access_token: str, tool_id: str, plan_id: str, duration_days: int) -> None:
    """Создаёт или обновляет подписку пользователя на инструмент."""
    from datetime import datetime, timezone, timedelta
    expires_at = (datetime.now(timezone.utc) + timedelta(days=duration_days)).isoformat()

    user_r = requests.get(f"{AUTH_URL}/user", headers=_auth_headers(access_token), timeout=10)
    user_id = user_r.json().get("id")

    existing = requests.get(
        f"{REST_URL}/subscriptions?user_id=eq.{user_id}&tool_id=eq.{tool_id}&select=id",
        headers=_auth_headers(access_token),
        timeout=15,
    )

    payload = {
        "tool_id":    tool_id,
        "plan_id":    plan_id,
        "expires_at": expires_at,
        "status":     "active",
        "source":     "yookassa",
    }

    if existing.ok and existing.json():
        sub_id = existing.json()[0]["id"]
        requests.patch(
            f"{REST_URL}/subscriptions?id=eq.{sub_id}",
            headers={**_auth_headers(access_token), "Prefer": "return=minimal"},
            json=payload,
            timeout=15,
        )
    else:
        payload["user_id"] = user_id
        requests.post(
            f"{REST_URL}/subscriptions",
            headers={**_auth_headers(access_token), "Prefer": "return=minimal"},
            json=payload,
            timeout=15,
        )


def get_trial(access_token: str, tool_id: str) -> int:
    """Возвращает количество использованных пробных откликов (0 если не начат)."""
    r = requests.get(
        f"{REST_URL}/trials?tool_id=eq.{tool_id}&select=responses_used",
        headers=_auth_headers(access_token),
        timeout=10,
    )
    if r.ok and r.json():
        return r.json()[0].get("responses_used", 0)
    return 0


def increment_trial(access_token: str, tool_id: str) -> int:
    """Увеличивает счётчик пробных откликов на 1. Возвращает новое значение."""
    user_r = requests.get(f"{AUTH_URL}/user", headers=_auth_headers(access_token), timeout=10)
    user_id = user_r.json().get("id")

    existing = requests.get(
        f"{REST_URL}/trials?user_id=eq.{user_id}&tool_id=eq.{tool_id}&select=id,responses_used",
        headers=_auth_headers(access_token),
        timeout=10,
    )
    if existing.ok and existing.json():
        row = existing.json()[0]
        new_val = row["responses_used"] + 1
        requests.patch(
            f"{REST_URL}/trials?id=eq.{row['id']}",
            headers={**_auth_headers(access_token), "Prefer": "return=minimal"},
            json={"responses_used": new_val},
            timeout=10,
        )
        return new_val
    else:
        requests.post(
            f"{REST_URL}/trials",
            headers={**_auth_headers(access_token), "Prefer": "return=minimal"},
            json={"user_id": user_id, "tool_id": tool_id, "responses_used": 1},
            timeout=10,
        )
        return 1


# ── Subscriptions ─────────────────────────────────────────────────────────────

def get_subscriptions(access_token: str) -> list[dict]:
    r = requests.get(
        f"{REST_URL}/subscriptions?select=*,tools(slug,name),plans(name,duration_days)",
        headers=_auth_headers(access_token),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def create_payment(access_token: str, plan_id: str, user_id: str) -> dict:
    r = requests.post(
        f"{FUNCTIONS_URL}/create-payment",
        headers=_auth_headers(access_token),
        json={"plan_id": plan_id, "user_id": user_id},
        timeout=20,
    )
    data = r.json()
    if not r.ok:
        raise RuntimeError(data.get("error") or "Ошибка создания платежа")
    return data


def get_subscription(access_token: str, tool_id: str) -> dict | None:
    r = requests.get(
        f"{REST_URL}/subscriptions?tool_id=eq.{tool_id}&select=*",
        headers=_auth_headers(access_token),
        timeout=15,
    )
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else None


def get_payments(access_token: str) -> list[dict]:
    r = requests.get(
        f"{REST_URL}/payments?select=*&order=created_at.desc&limit=30",
        headers=_auth_headers(access_token),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()
