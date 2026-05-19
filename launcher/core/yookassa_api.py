import uuid
import requests

_SHOP_ID   = "1353662"
_SECRET    = "live_QFLgQEKALBc_IR9qE4wA9Whgeu79E7IEMSq-acJf4MA"
_BASE      = "https://api.yookassa.ru/v3"
_RETURN_URL = "https://romakotel30-cell.github.io/vacantrix-web/"


def create_payment(amount_rub: int, plan_name: str, days: int,
                   tool_label: str, customer_email: str | None = None) -> dict:
    """Создаёт платёж. Возвращает {payment_id, confirmation_url}."""
    description = f"Vacantrix {tool_label} · {plan_name} · {days} дн."

    body = {
        "amount":       {"value": f"{amount_rub:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": _RETURN_URL},
        "capture":      True,
        "description":  description,
        "metadata":     {"plan": plan_name, "days": days, "tool": tool_label},
    }

    if customer_email:
        body["receipt"] = {
            "customer": {"email": customer_email},
            "items": [{
                "description":   description,
                "quantity":      "1.00",
                "amount":        {"value": f"{amount_rub:.2f}", "currency": "RUB"},
                "vat_code":      1,
                "payment_mode":  "full_payment",
                "payment_subject": "service",
            }],
        }

    r = requests.post(
        f"{_BASE}/payments",
        auth=(_SHOP_ID, _SECRET),
        headers={
            "Idempotence-Key": str(uuid.uuid4()),
            "Content-Type": "application/json",
        },
        json=body,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    return {
        "payment_id":       data["id"],
        "confirmation_url": data["confirmation"]["confirmation_url"],
    }


def get_payment_status(payment_id: str) -> str:
    """Возвращает статус: pending / waiting_for_capture / succeeded / canceled."""
    r = requests.get(
        f"{_BASE}/payments/{payment_id}",
        auth=(_SHOP_ID, _SECRET),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["status"]
