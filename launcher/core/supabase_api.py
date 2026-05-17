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
        f"{REST_URL}/payments?select=*,plans(name,duration_days,tools(name))&order=created_at.desc&limit=30",
        headers=_auth_headers(access_token),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()
