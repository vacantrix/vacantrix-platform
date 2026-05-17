from datetime import datetime, timezone
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar, QTabWidget,
)

from launcher.core.auth_manager import AuthManager
from launcher.core import supabase_api as api


class _DataWorker(QThread):
    done  = Signal(list, list)   # subs, payments
    error = Signal(str)

    def __init__(self, token: str):
        super().__init__()
        self._token = token

    def run(self):
        try:
            subs     = api.get_subscriptions(self._token)
            payments = api.get_payments(self._token)
            self.done.emit(subs, payments)
        except Exception as e:
            self.error.emit(str(e))


def _fmt_dt(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return iso


def _days_left(iso: str) -> int:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return max(0, (dt - datetime.now(tz=timezone.utc)).days)
    except Exception:
        return 0


class CabinetScreen(QWidget):
    back_requested = Signal()

    def __init__(self, auth: AuthManager, parent=None):
        super().__init__(parent)
        self._auth   = auth
        self._worker = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QFrame()
        header.setProperty("class", "header")
        header.setFixedHeight(52)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 0, 16, 0)

        back = QPushButton("← Назад")
        back.setProperty("class", "flat")
        back.setFixedHeight(30)
        back.clicked.connect(self.back_requested)
        h_lay.addWidget(back)

        title = QLabel("Личный кабинет")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #eeeef5;")
        title.setAlignment(Qt.AlignCenter)
        h_lay.addWidget(title, stretch=1)

        refresh = QPushButton("⟳")
        refresh.setFixedSize(32, 32)
        refresh.clicked.connect(self.load)
        h_lay.addWidget(refresh)
        root.addWidget(header)

        # Body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        b_lay = QVBoxLayout(body)
        b_lay.setContentsMargins(28, 24, 28, 24)
        b_lay.setSpacing(20)

        # Profile card
        profile = QFrame()
        profile.setProperty("class", "card")
        p_lay = QHBoxLayout(profile)
        p_lay.setContentsMargins(20, 16, 20, 16)

        avatar = QLabel("👤")
        avatar.setStyleSheet("font-size: 40px;")
        p_lay.addWidget(avatar)

        p_info = QVBoxLayout()
        user = self._auth.user or {}
        self._email_lbl = QLabel(user.get("email", "—"))
        self._email_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #eeeef5;")
        p_info.addWidget(self._email_lbl)
        since_raw = user.get("created_at", "")
        since = _fmt_dt(since_raw)[:10] if since_raw else "—"
        since_lbl = QLabel(f"Участник с {since}")
        since_lbl.setStyleSheet("color: #666; font-size: 11px;")
        p_info.addWidget(since_lbl)
        p_lay.addLayout(p_info)
        p_lay.addStretch()

        b_lay.addWidget(profile)

        # Tabs: подписки / платежи
        tabs = QTabWidget()

        # ── Tab 1: Подписки ──
        subs_tab = QWidget()
        st_lay = QVBoxLayout(subs_tab)
        st_lay.setContentsMargins(0, 12, 0, 0)
        st_lay.setSpacing(12)

        self._subs_container = QVBoxLayout()
        self._subs_container.setSpacing(10)
        self._no_subs = QLabel("Нет активных подписок")
        self._no_subs.setAlignment(Qt.AlignCenter)
        self._no_subs.setStyleSheet("color: #555; font-size: 13px; padding: 20px;")
        self._subs_container.addWidget(self._no_subs)
        st_lay.addLayout(self._subs_container)
        st_lay.addStretch()
        tabs.addTab(subs_tab, "Подписки")

        # ── Tab 2: История платежей ──
        pay_tab = QWidget()
        pt_lay = QVBoxLayout(pay_tab)
        pt_lay.setContentsMargins(0, 12, 0, 0)

        self._pay_table = QTableWidget(0, 4)
        self._pay_table.setHorizontalHeaderLabels(["Дата", "Инструмент", "Тариф", "Сумма"])
        self._pay_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._pay_table.verticalHeader().setVisible(False)
        self._pay_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._pay_table.setSelectionMode(QTableWidget.NoSelection)
        self._pay_table.setAlternatingRowColors(True)
        pt_lay.addWidget(self._pay_table)
        tabs.addTab(pay_tab, "История платежей")

        b_lay.addWidget(tabs)

        self._status_lbl = QLabel("")
        self._status_lbl.setAlignment(Qt.AlignCenter)
        self._status_lbl.setStyleSheet("color: #555; font-size: 11px;")
        b_lay.addWidget(self._status_lbl)

        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

    def preload(self, token: str):
        """Called once after login — loads data in background silently."""
        self.load()

    def load(self):
        self._status_lbl.setText("Загрузка...")
        self._worker = _DataWorker(self._auth.access_token)
        self._worker.done.connect(self._on_loaded)
        self._worker.error.connect(lambda e: self._status_lbl.setText(f"Ошибка: {e}"))
        self._worker.start()

    def _on_loaded(self, subs: list, payments: list):
        self._fill_subs(subs)
        self._fill_payments(payments)
        self._status_lbl.setText("")

    def _fill_subs(self, subs: list):
        # Clear container (keep no_subs label)
        while self._subs_container.count():
            item = self._subs_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not subs:
            self._subs_container.addWidget(self._no_subs)
            self._no_subs.show()
            return

        self._no_subs.hide()
        for sub in subs:
            card = self._make_sub_card(sub)
            self._subs_container.addWidget(card)

    def _make_sub_card(self, sub: dict) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        tool_name = sub.get("tools", {}).get("name", "—")
        plan_name = sub.get("plans", {}).get("name", "—")
        expires   = sub.get("expires_at", "")
        days      = _days_left(expires)
        duration  = sub.get("plans", {}).get("duration_days", 30)
        active    = sub.get("status") == "active"

        top = QHBoxLayout()
        name_lbl = QLabel(tool_name)
        name_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #eeeef5;")
        top.addWidget(name_lbl)
        top.addStretch()

        status_lbl = QLabel("✅ Активна" if active else "⛔ Истекла")
        status_lbl.setStyleSheet(
            f"color: {'#4caf50' if active else '#c41c1c'}; font-size: 12px; font-weight: bold;"
        )
        top.addWidget(status_lbl)
        lay.addLayout(top)

        plan_lbl = QLabel(f"Тариф: {plan_name}   •   Истекает: {_fmt_dt(expires)[:10] if expires else '—'}")
        plan_lbl.setStyleSheet("color: #888; font-size: 11px;")
        lay.addWidget(plan_lbl)

        if active and duration > 0:
            bar = QProgressBar()
            bar.setRange(0, duration)
            bar.setValue(min(days, duration))
            bar.setFormat(f"{days} дн. осталось")
            bar.setFixedHeight(16)
            lay.addWidget(bar)

        return card

    def _fill_payments(self, payments: list):
        self._pay_table.setRowCount(len(payments))
        STATUS_MAP = {"succeeded": "✅ Оплачен", "pending": "⏳ Ожидает", "cancelled": "❌ Отменён"}
        for i, p in enumerate(payments):
            date     = _fmt_dt(p.get("paid_at") or p.get("created_at", ""))
            tool     = (p.get("plans") or {}).get("tools", {}).get("name", "—") if p.get("plans") else "—"
            plan     = (p.get("plans") or {}).get("name", "—")
            amount   = f"{p.get('amount_rub', 0)} ₽"

            for col, val in enumerate([date, tool, plan, amount]):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                self._pay_table.setItem(i, col, item)
