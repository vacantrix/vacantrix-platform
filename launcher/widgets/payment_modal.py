import webbrowser
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QMessageBox, QTabWidget, QWidget, QScrollArea,
)
from PySide6.QtGui import QFont
from launcher.core import supabase_api as api
from launcher.core import yookassa_api as yk
from launcher.core.auth_manager import AuthManager

_HH_ID    = "82cadb47-0ee6-473c-a5f5-b9eba08b282f"
_AVITO_ID = "4d2fd775-c120-4a4c-b8df-cb662067777f"

# Эмодзи-иконки для каждого тарифа (по duration_days)
_ICONS = {1: "⚡", 2: "🥊", 3: "🏃", 4: "🎸", 5: "📅",
          10: "🎯", 20: "🏅", 30: "🚀"}


class _LoadWorker(QThread):
    done  = Signal(list, list, list)
    error = Signal(str)

    def run(self):
        try:
            all_plans = api.get_all_plans()
            hh    = [p for p in all_plans if p.get("tool_id") == _HH_ID    and not p.get("is_combo")]
            avito = [p for p in all_plans if p.get("tool_id") == _AVITO_ID and not p.get("is_combo")]
            combo = [p for p in all_plans if p.get("is_combo")]
            self.done.emit(hh, avito, combo)
        except Exception as e:
            self.error.emit(str(e))


class _PayWorker(QThread):
    done  = Signal(str, str)   # confirmation_url, payment_id
    error = Signal(str)

    def __init__(self, plan: dict, email: str | None = None):
        super().__init__()
        self._plan  = plan
        self._email = email

    def run(self):
        try:
            name  = self._plan.get("name", "Подписка")
            days  = self._plan.get("duration_days", 1)
            price = self._plan.get("price_rub", 0)
            tool  = "HH.ru + Авито" if self._plan.get("is_combo") else (
                    "Авито" if self._plan.get("tool_id") == _AVITO_ID else "HH.ru")
            result = yk.create_payment(price, name, days, tool, self._email)
            self.done.emit(result["confirmation_url"], result["payment_id"])
        except Exception as e:
            self.error.emit(str(e))


class _PollWorker(QThread):
    activated = Signal()
    failed    = Signal()

    def __init__(self, access_token: str, payment_id: str, plan: dict):
        super().__init__()
        self._token      = access_token
        self._payment_id = payment_id
        self._plan       = plan
        self._stop       = False

    def run(self):
        import time
        for _ in range(40):          # 40 × 3 сек = 2 минуты
            if self._stop:
                return
            try:
                status = yk.get_payment_status(self._payment_id)
                if status == "succeeded":
                    self._activate()
                    self.activated.emit()
                    return
                if status == "canceled":
                    self.failed.emit()
                    return
            except Exception:
                pass
            time.sleep(3)

    def _activate(self):
        plan     = self._plan
        duration = plan.get("duration_days", 1)
        plan_id  = plan["id"]
        if plan.get("is_combo"):
            for tool_id in api.get_plan_tool_ids(plan_id):
                api.activate_subscription(self._token, tool_id, plan_id, duration)
        else:
            tool_id = plan.get("tool_id")
            if tool_id:
                api.activate_subscription(self._token, tool_id, plan_id, duration)

    def stop(self):
        self._stop = True


def _sep():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("background: rgba(200,25,25,50); max-height:1px; border:none;")
    return f


def _scrollable(inner: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setWidget(inner)
    return scroll


class PaymentModal(QDialog):
    payment_done = Signal()

    def __init__(self, tool: dict, auth: AuthManager, parent=None):
        super().__init__(parent)
        self._tool        = tool
        self._auth        = auth
        self._selected    = None
        self._pay_worker  = None
        self._poll_worker = None
        self._load_worker = None

        self.setWindowTitle("Подписка — Vacantrix")
        self.setMinimumWidth(500)
        self.setMinimumHeight(560)
        self.setModal(True)
        self._build()
        self._load_plans()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Выберите тариф")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 17px; font-weight: bold; color: #eeeef5; letter-spacing: 0.5px;")
        lay.addWidget(title)

        self._tabs = QTabWidget()
        lay.addWidget(self._tabs, stretch=1)

        self._status = QLabel("Загрузка тарифов...")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setStyleSheet("color: #666; font-size: 12px;")
        lay.addWidget(self._status)

        btn_row = QHBoxLayout()
        self._pay_btn = QPushButton("Оплатить")
        self._pay_btn.setFixedHeight(44)
        self._pay_btn.setEnabled(False)
        self._pay_btn.clicked.connect(self._do_pay)
        btn_row.addWidget(self._pay_btn)

        cancel = QPushButton("Отмена")
        cancel.setFixedHeight(44)
        cancel.setProperty("class", "secondary")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        lay.addLayout(btn_row)

    def _load_plans(self):
        self._load_worker = _LoadWorker()
        self._load_worker.done.connect(self._on_plans)
        self._load_worker.error.connect(lambda e: self._status.setText(f"Ошибка: {e}"))
        self._load_worker.start()

    def _on_plans(self, hh, avito, combo):
        self._status.setText("Выберите тариф и нажмите «Оплатить»")
        self._tabs.clear()
        self._tabs.addTab(_scrollable(self._build_plans_page(hh)),    "🔴  HH.ru")
        self._tabs.addTab(_scrollable(self._build_plans_page(avito)), "🟡  Авито")
        self._tabs.addTab(_scrollable(self._build_combo_page(combo)), "🔥  Комбо")
        if self._tool.get("slug") == "avito":
            self._tabs.setCurrentIndex(1)

    # ── Вкладки ──────────────────────────────────────────────────────────────

    def _build_plans_page(self, plans: list) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(12, 14, 12, 14)
        lay.setSpacing(10)

        if not plans:
            lbl = QLabel("Тарифы скоро появятся")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #555; padding: 30px;")
            lay.addWidget(lbl)
        else:
            for plan in plans:
                lay.addWidget(self._plan_card(plan))

        lay.addStretch()
        return page

    def _build_combo_page(self, plans: list) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(12, 14, 12, 14)
        lay.setSpacing(10)

        banner = QFrame()
        banner.setStyleSheet(
            "QFrame { background: rgba(255,180,0,12); border: 1px solid rgba(255,180,0,50);"
            "border-radius: 10px; }"
        )
        bl = QVBoxLayout(banner)
        bl.setContentsMargins(14, 10, 14, 10)
        bl.setSpacing(2)
        t1 = QLabel("🔥  HH.ru + Авито — один тариф")
        t1.setAlignment(Qt.AlignCenter)
        t1.setStyleSheet("color: #ffd060; font-size: 13px; font-weight: bold;")
        t2 = QLabel("В 1.5 раза дешевле, чем покупать каждый инструмент отдельно")
        t2.setAlignment(Qt.AlignCenter)
        t2.setStyleSheet("color: #4caf50; font-size: 11px;")
        bl.addWidget(t1)
        bl.addWidget(t2)
        lay.addWidget(banner)

        for plan in plans:
            lay.addWidget(self._combo_card(plan))

        lay.addStretch()
        return page

    # ── Карточки тарифов ─────────────────────────────────────────────────────

    def _plan_card(self, plan: dict) -> QFrame:
        days  = plan.get("duration_days", 0)
        icon  = _ICONS.get(days, "✦")
        name  = plan.get("name", f"{days} дн.")
        price = plan.get("price_rub", 0)

        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: rgba(18,6,6,200); border: 1px solid rgba(200,25,25,70);"
            "border-radius: 12px; }"
            "QFrame:hover { border: 1px solid rgba(255,60,60,160);"
            "background: rgba(28,8,8,220); }"
        )
        cl = QHBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(14)

        # Иконка-круг
        icon_lbl = QLabel(icon)
        icon_lbl.setFixedSize(42, 42)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(
            "font-size: 20px; background: rgba(200,25,25,25);"
            "border: 1px solid rgba(200,25,25,80); border-radius: 21px;"
            "padding: 0;"
        )
        icon_font = QFont()
        icon_font.setFamilies(["Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji"])
        icon_font.setPointSize(16)
        icon_lbl.setFont(icon_font)
        cl.addWidget(icon_lbl)

        # Название + срок
        info = QVBoxLayout()
        info.setSpacing(2)

        name_lbl = QLabel(name)
        name_font = QFont()
        name_font.setPointSize(13)
        name_font.setBold(True)
        name_font.setLetterSpacing(QFont.AbsoluteSpacing, 0.3)
        name_lbl.setFont(name_font)
        name_lbl.setStyleSheet("color: #eeeef5; background: transparent;")
        info.addWidget(name_lbl)

        days_lbl = QLabel(f"{days} {'день' if days == 1 else 'дня' if days < 5 else 'дней'}")
        days_lbl.setStyleSheet("color: #555; font-size: 11px; background: transparent;")
        info.addWidget(days_lbl)

        cl.addLayout(info)
        cl.addStretch()

        # Цена
        price_lbl = QLabel(f"{price} ₽")
        pf = QFont()
        pf.setPointSize(15)
        pf.setBold(True)
        price_lbl.setFont(pf)
        price_lbl.setStyleSheet("color: #ff5555; background: transparent;")
        cl.addWidget(price_lbl)

        # Кнопка
        btn = QPushButton("Выбрать")
        btn.setFixedSize(90, 34)
        btn.setProperty("class", "secondary")
        btn.clicked.connect(lambda _, p=plan: self._select(p))
        cl.addWidget(btn)

        # Бейдж «Популярно»
        if plan.get("is_popular"):
            badge = QLabel("★ Топ")
            badge.setStyleSheet(
                "background: rgba(255,180,0,20); color: #ffd060;"
                "border: 1px solid rgba(255,180,0,80); border-radius: 8px;"
                "font-size: 10px; padding: 2px 8px;"
            )
            cl.addWidget(badge)

        return card

    def _combo_card(self, plan: dict) -> QFrame:
        days      = plan.get("duration_days", 0)
        icon      = _ICONS.get(days, "✦")
        name      = plan.get("name", f"Комбо {days} дн.")
        combo_p   = plan.get("price_rub", 0)
        single_p  = round(combo_p / 1.5)
        separate  = single_p * 2
        saving    = separate - combo_p

        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: rgba(24,16,0,200); border: 1px solid rgba(255,180,0,60);"
            "border-radius: 12px; }"
            "QFrame:hover { border: 1px solid rgba(255,200,60,150);"
            "background: rgba(32,20,0,220); }"
        )
        cl = QHBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(14)

        icon_lbl = QLabel(icon)
        icon_lbl.setFixedSize(42, 42)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(
            "font-size: 20px; background: rgba(255,180,0,15);"
            "border: 1px solid rgba(255,180,0,60); border-radius: 21px; padding: 0;"
        )
        icon_font = QFont()
        icon_font.setFamilies(["Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji"])
        icon_font.setPointSize(16)
        icon_lbl.setFont(icon_font)
        cl.addWidget(icon_lbl)

        info = QVBoxLayout()
        info.setSpacing(2)

        # Убираем "Комбо - " из отображаемого названия
        short_name = name.replace("Комбо - ", "").replace("Комбо · ", "")
        name_lbl = QLabel(short_name)
        nf = QFont()
        nf.setPointSize(13)
        nf.setBold(True)
        nf.setLetterSpacing(QFont.AbsoluteSpacing, 0.3)
        name_lbl.setFont(nf)
        name_lbl.setStyleSheet("color: #eeeef5; background: transparent;")
        info.addWidget(name_lbl)

        days_lbl = QLabel(f"HH.ru + Авито  •  {days} {'день' if days==1 else 'дня' if days<5 else 'дней'}")
        days_lbl.setStyleSheet("color: #666; font-size: 11px; background: transparent;")
        info.addWidget(days_lbl)

        if saving > 0:
            save_lbl = QLabel(f"Экономия {saving} ₽  (отдельно {separate} ₽)")
            save_lbl.setStyleSheet("color: #4caf50; font-size: 11px; background: transparent;")
            info.addWidget(save_lbl)

        cl.addLayout(info)
        cl.addStretch()

        price_lbl = QLabel(f"{combo_p} ₽")
        pf = QFont()
        pf.setPointSize(15)
        pf.setBold(True)
        price_lbl.setFont(pf)
        price_lbl.setStyleSheet("color: #ffd060; background: transparent;")
        cl.addWidget(price_lbl)

        btn = QPushButton("Выбрать")
        btn.setFixedSize(90, 34)
        btn.setProperty("class", "secondary")
        btn.clicked.connect(lambda _, p=plan: self._select(p))
        cl.addWidget(btn)

        if plan.get("is_popular"):
            badge = QLabel("🔥 Хит")
            badge.setStyleSheet(
                "background: rgba(255,180,0,20); color: #ffd060;"
                "border: 1px solid rgba(255,180,0,80); border-radius: 8px;"
                "font-size: 10px; padding: 2px 8px;"
            )
            badge.setFont(icon_font)
            cl.addWidget(badge)

        return card

    # ── Actions ──────────────────────────────────────────────────────────────

    def _select(self, plan: dict):
        self._selected = plan
        self._pay_btn.setEnabled(True)
        name  = plan.get("name", "")
        price = plan.get("price_rub", 0)
        self._status.setText(f"Выбрано: {name} — {price} ₽")

    def _do_pay(self):
        if not self._selected:
            return
        self._pay_btn.setEnabled(False)
        self._status.setText("Создаём платёж...")
        email = (self._auth.user or {}).get("email")
        self._pay_worker = _PayWorker(self._selected, email)
        self._pay_worker.done.connect(self._on_payment_created)
        self._pay_worker.error.connect(self._on_error)
        self._pay_worker.start()

    def _on_payment_created(self, confirmation_url: str, payment_id: str):
        # Прячем вкладки и показываем карточку ожидания
        self._tabs.hide()
        self._pay_btn.hide()
        self._show_waiting_card(confirmation_url)

        self._poll_worker = _PollWorker(
            self._auth.access_token, payment_id, self._selected
        )
        self._poll_worker.activated.connect(self._on_activated)
        self._poll_worker.failed.connect(self._on_payment_failed)
        self._poll_worker.finished.connect(self._on_poll_timeout)
        self._poll_worker.start()

    def _show_waiting_card(self, url: str):
        plan  = self._selected
        name  = plan.get("name", "")
        days  = plan.get("duration_days", 1)
        price = plan.get("price_rub", 0)
        is_combo = plan.get("is_combo", False)
        tool  = "HH.ru + Авито" if is_combo else (
                "Авито" if plan.get("tool_id") == _AVITO_ID else "HH.ru")
        icon  = _ICONS.get(days, "✦")

        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: rgba(18,10,4,220); border: 1px solid rgba(200,25,25,80);"
            "border-radius: 14px; }"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 20, 24, 20)
        cl.setSpacing(10)

        # Иконка + название
        top = QHBoxLayout()
        icon_lbl = QLabel(icon)
        icon_lbl.setFixedSize(48, 48)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(
            "font-size: 24px; background: rgba(200,25,25,20);"
            "border: 1px solid rgba(200,25,25,70); border-radius: 24px; padding: 0;"
        )
        ef = QFont()
        ef.setFamilies(["Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji"])
        ef.setPointSize(18)
        icon_lbl.setFont(ef)
        top.addWidget(icon_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        name_lbl = QLabel(name)
        nf = QFont(); nf.setPointSize(14); nf.setBold(True)
        name_lbl.setFont(nf)
        name_lbl.setStyleSheet("color: #eeeef5; background: transparent;")
        title_col.addWidget(name_lbl)

        sub_lbl = QLabel(
            f"{tool}  •  {days} {'день' if days==1 else 'дня' if days<5 else 'дней'}"
        )
        sub_lbl.setStyleSheet("color: #666; font-size: 12px; background: transparent;")
        title_col.addWidget(sub_lbl)
        top.addLayout(title_col)
        top.addStretch()

        price_lbl = QLabel(f"{price} ₽")
        pf = QFont(); pf.setPointSize(18); pf.setBold(True)
        price_lbl.setFont(pf)
        price_lbl.setStyleSheet("color: #ff5555; background: transparent;")
        top.addWidget(price_lbl)
        cl.addLayout(top)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: rgba(200,25,25,40); max-height:1px; border:none;")
        cl.addWidget(sep)

        # Статус + кнопка открыть
        status_row = QHBoxLayout()
        self._wait_lbl = QLabel("⏳  Ожидаем оплаты...")
        self._wait_lbl.setStyleSheet("color: #ffd060; font-size: 12px; background: transparent;")
        status_row.addWidget(self._wait_lbl)
        status_row.addStretch()

        open_btn = QPushButton("Открыть страницу →")
        open_btn.setFixedHeight(32)
        open_btn.setProperty("class", "secondary")
        open_btn.clicked.connect(lambda: webbrowser.open(url))
        status_row.addWidget(open_btn)
        cl.addLayout(status_row)

        hint = QLabel("Браузер открыт. После оплаты подписка активируется автоматически.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #444; font-size: 11px; background: transparent;")
        cl.addWidget(hint)

        # Вставляем карточку в layout между вкладками и статусом
        lay = self.layout()
        lay.insertWidget(1, card)
        self._waiting_card = card
        self._status.setText("")

        webbrowser.open(url)

    def _on_activated(self):
        if hasattr(self, "_waiting_card"):
            self._waiting_card.hide()
        QMessageBox.information(self, "Готово", "✅  Подписка успешно активирована!")
        self.payment_done.emit()
        self.accept()

    def _on_payment_failed(self):
        self._restore_tabs()
        self._status.setText("❌ Платёж отменён.")

    def _on_poll_timeout(self):
        if self._poll_worker and not self._poll_worker._stop:
            self._restore_tabs()
            self._status.setText("Платёж не подтверждён за 2 мин. Обновите статус в каталоге.")

    def _restore_tabs(self):
        if hasattr(self, "_waiting_card"):
            self._waiting_card.hide()
        self._tabs.show()
        self._pay_btn.show()
        self._pay_btn.setEnabled(True)

    def _on_error(self, msg: str):
        self._pay_btn.setEnabled(True)
        self._status.setText(f"Ошибка: {msg}")

    def closeEvent(self, event):
        if self._poll_worker:
            self._poll_worker.stop()
        super().closeEvent(event)
