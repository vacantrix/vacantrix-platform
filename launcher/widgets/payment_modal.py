import webbrowser
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QButtonGroup, QFrame, QMessageBox,
)

from launcher.core import supabase_api as api
from launcher.core.auth_manager import AuthManager


class _PlansWorker(QThread):
    done  = Signal(list)
    error = Signal(str)

    def __init__(self, tool_id: str):
        super().__init__()
        self._tool_id = tool_id

    def run(self):
        try:
            self.done.emit(api.get_plans(self._tool_id))
        except Exception as e:
            self.error.emit(str(e))


class _PayWorker(QThread):
    done  = Signal(str, str)   # payment_url, payment_id
    error = Signal(str)

    def __init__(self, token: str, plan_id: str, user_id: str):
        super().__init__()
        self._token   = token
        self._plan_id = plan_id
        self._user_id = user_id

    def run(self):
        try:
            result = api.create_payment(self._token, self._plan_id, self._user_id)
            self.done.emit(result["payment_url"], result["payment_id"])
        except Exception as e:
            self.error.emit(str(e))


class _PollWorker(QThread):
    activated = Signal()

    def __init__(self, token: str, tool_id: str, max_attempts: int = 20):
        super().__init__()
        self._token       = token
        self._tool_id     = tool_id
        self._max_attempts = max_attempts
        self._stop        = False

    def run(self):
        import time
        for _ in range(self._max_attempts):
            if self._stop:
                return
            try:
                sub = api.get_subscription(self._token, self._tool_id)
                if sub and sub.get("status") == "active":
                    self.activated.emit()
                    return
            except Exception:
                pass
            time.sleep(3)

    def stop(self):
        self._stop = True


class PaymentModal(QDialog):
    payment_done = Signal()   # subscription activated

    def __init__(self, tool: dict, auth: AuthManager, parent=None):
        super().__init__(parent)
        self._tool        = tool
        self._auth        = auth
        self._plans       = []
        self._selected    = None
        self._plans_worker = None
        self._pay_worker   = None
        self._poll_worker  = None

        self.setWindowTitle(f"Подписка — {tool['name']}")
        self.setMinimumWidth(380)
        self.setModal(True)
        self._build()
        self._load_plans()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        title = QLabel(f"Выберите тариф для <b>{self._tool['name']}</b>")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        self._plans_frame = QVBoxLayout()
        lay.addLayout(self._plans_frame)

        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setStyleSheet("color: #aaa; font-size: 12px;")
        lay.addWidget(self._status)

        self._pay_btn = QPushButton("Оплатить")
        self._pay_btn.setFixedHeight(42)
        self._pay_btn.setEnabled(False)
        self._pay_btn.setStyleSheet(
            "background: #4f8ef7; color: white; border-radius: 8px; font-size: 14px; font-weight: bold;"
        )
        self._pay_btn.clicked.connect(self._do_pay)
        lay.addWidget(self._pay_btn)

        cancel = QPushButton("Отмена")
        cancel.setFlat(True)
        cancel.setStyleSheet("color: #888;")
        cancel.clicked.connect(self.reject)
        lay.addWidget(cancel)

    def _load_plans(self):
        self._status.setText("Загрузка тарифов...")
        self._plans_worker = _PlansWorker(self._tool["id"])
        self._plans_worker.done.connect(self._on_plans)
        self._plans_worker.error.connect(lambda e: self._status.setText(e))
        self._plans_worker.start()

    def _on_plans(self, plans: list):
        self._plans = plans
        self._status.setText("Выберите тариф:")
        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)

        for plan in plans:
            btn = QPushButton(f"{plan['name']}  —  {plan['price_rub']} ₽")
            btn.setCheckable(True)
            btn.setFixedHeight(40)
            btn.setStyleSheet("""
                QPushButton { border: 2px solid #444; border-radius: 8px; }
                QPushButton:checked { border-color: #4f8ef7; background: #1a2a4a; color: #4f8ef7; font-weight: bold; }
            """)
            if plan.get("is_popular"):
                btn.setText(btn.text() + "  ⭐")
            btn.clicked.connect(lambda _, p=plan: self._select(p))
            self._btn_group.addButton(btn)
            self._plans_frame.addWidget(btn)

    def _select(self, plan: dict):
        self._selected = plan
        self._pay_btn.setEnabled(True)

    def _do_pay(self):
        if not self._selected:
            return
        self._pay_btn.setEnabled(False)
        self._status.setText("Создаём платёж...")

        user_id = self._auth.user["id"]
        self._pay_worker = _PayWorker(
            self._auth.access_token,
            self._selected["id"],
            user_id,
        )
        self._pay_worker.done.connect(self._on_payment_created)
        self._pay_worker.error.connect(self._on_error)
        self._pay_worker.start()

    def _on_payment_created(self, payment_url: str, payment_id: str):
        self._status.setText("Ожидаем оплаты...")
        webbrowser.open(payment_url)
        self._start_polling()

    def _start_polling(self):
        self._poll_worker = _PollWorker(
            self._auth.access_token,
            self._tool["id"],
        )
        self._poll_worker.activated.connect(self._on_activated)
        self._poll_worker.finished.connect(self._on_poll_timeout)
        self._poll_worker.start()

    def _on_activated(self):
        self._status.setText("✅ Подписка активирована!")
        QMessageBox.information(self, "Готово", "Подписка активирована!")
        self.payment_done.emit()
        self.accept()

    def _on_poll_timeout(self):
        if not self._poll_worker or self._poll_worker._stop:
            return
        self._status.setText("Оплата не обнаружена. Нажмите «Обновить» в каталоге.")
        self._pay_btn.setEnabled(True)

    def _on_error(self, msg: str):
        self._pay_btn.setEnabled(True)
        self._status.setText(f"Ошибка: {msg}")

    def closeEvent(self, event):
        if self._poll_worker:
            self._poll_worker.stop()
        super().closeEvent(event)
