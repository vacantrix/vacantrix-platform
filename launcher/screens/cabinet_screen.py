import json
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar, QTabWidget,
    QLineEdit, QGridLayout,
)

from launcher.core.auth_manager import AuthManager
from launcher.core import supabase_api as api
from launcher.core import vx_profile as vxp

from launcher.paths import RESOURCES as _RES_DIR
_PREFS_FILE    = Path(__file__).parent.parent.parent / "data" / "preferences.json"
_REFRESH_IMG   = _RES_DIR / "Кнопка обновить.png"

AVATAR_EMOJIS = [
    "👤", "😊", "😎", "🚀", "💼", "🔥", "⚡", "🎯",
    "🦊", "🤖", "💡", "🌟", "🛡️", "💎", "🦅", "👾",
]


def _load_prefs() -> dict:
    if _PREFS_FILE.exists():
        try:
            return json.loads(_PREFS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_prefs(data: dict) -> None:
    try:
        _PREFS_FILE.parent.mkdir(exist_ok=True)
        existing = _load_prefs()
        existing.update(data)
        _PREFS_FILE.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _fmt_dt(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y")
    except Exception:
        return iso


def _days_left(iso: str) -> int:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return max(0, (dt - datetime.now(tz=timezone.utc)).days)
    except Exception:
        return 0


class _DataWorker(QThread):
    done = Signal(list, list)
    error = Signal(str)

    def __init__(self, token: str):
        super().__init__()
        self._token = token

    def run(self):
        try:
            subs = api.get_subscriptions(self._token)
        except Exception as e:
            self.error.emit(str(e))
            return
        try:
            payments = api.get_payments(self._token)
        except Exception:
            payments = []
        self.done.emit(subs, payments)


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("background: rgba(200,25,25,40); max-height: 1px; border: none;")
    return f


class CabinetScreen(QWidget):
    back_requested = Signal()
    logout_requested = Signal()

    def __init__(self, auth: AuthManager, parent=None):
        super().__init__(parent)
        self._auth = auth
        self._worker = None
        self._prefs = _load_prefs()
        self._build()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_refresh_btn(self, size: int = 32) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(size, size)
        btn.setToolTip("Обновить данные")
        btn.clicked.connect(self.load)
        if _REFRESH_IMG.exists():
            px = QPixmap(str(_REFRESH_IMG)).scaled(
                size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            btn.setIcon(QIcon(px))
            btn.setIconSize(QSize(size, size))
            btn.setStyleSheet(
                "QPushButton { background: transparent; border: none; }"
                "QPushButton:hover { background: rgba(185,22,22,30); border-radius: 6px; }"
                "QPushButton:pressed { background: rgba(185,22,22,60); border-radius: 6px; }"
            )
        else:
            btn.setText("⟳")
        return btn

    # ── Build ─────────────────────────────────────────────────────────────────

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

        logout_btn = QPushButton("Выйти")
        logout_btn.setProperty("class", "flat")
        logout_btn.setFixedHeight(30)
        logout_btn.setStyleSheet(
            "QPushButton { color: #c44; font-size: 12px; padding: 0 10px; }"
            "QPushButton:hover { color: #f66; }"
        )
        logout_btn.clicked.connect(self.logout_requested)
        h_lay.addWidget(logout_btn)

        h_lay.addWidget(self._make_refresh_btn(44))
        root.addWidget(header)

        # Body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        b_lay = QVBoxLayout(body)
        b_lay.setContentsMargins(28, 24, 28, 24)
        b_lay.setSpacing(16)

        b_lay.addWidget(self._build_profile_card())
        b_lay.addLayout(self._build_stats_row())
        b_lay.addWidget(self._build_tabs())

        self._status_lbl = QLabel("")
        self._status_lbl.setAlignment(Qt.AlignCenter)
        self._status_lbl.setStyleSheet("color: #444; font-size: 11px;")
        b_lay.addWidget(self._status_lbl)

        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

    def _build_profile_card(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(16)

        # Avatar circle
        self._avatar_lbl = QLabel(self._prefs.get("avatar_emoji", "👤"))
        self._avatar_lbl.setFixedSize(64, 64)
        self._avatar_lbl.setAlignment(Qt.AlignCenter)
        self._avatar_lbl.setStyleSheet(
            "font-size: 34px;"
            "background: rgba(185,22,22,18);"
            "border: 1px solid rgba(185,22,22,70);"
            "border-radius: 32px;"
        )
        top.addWidget(self._avatar_lbl)

        # Name + email + since
        user = self._auth.user or {}
        email = user.get("email", "—")
        since_raw = user.get("created_at", "")
        since = _fmt_dt(since_raw) if since_raw else "—"

        stored = self._prefs.get("display_name", "")
        display = stored or email.split("@")[0]

        info = QVBoxLayout()
        info.setSpacing(4)

        self._display_name_lbl = QLabel(display)
        self._display_name_lbl.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #eeeef5;"
        )
        info.addWidget(self._display_name_lbl)

        email_lbl = QLabel(email)
        email_lbl.setStyleSheet("color: #4a3a3a; font-size: 11px;")
        info.addWidget(email_lbl)

        since_lbl = QLabel(f"📅  Участник с {since}")
        since_lbl.setStyleSheet("color: #3a2a2a; font-size: 11px;")
        info.addWidget(since_lbl)

        top.addLayout(info)
        top.addStretch()
        lay.addLayout(top)

        return card

    def _build_stats_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        self._stat_subs = self._make_stat_card("—", "Активных подписок")
        self._stat_days = self._make_stat_card("—", "Дней до конца")
        row.addWidget(self._stat_subs)
        row.addWidget(self._stat_days)
        return row

    def _make_stat_card(self, value: str, label: str) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(4)
        lay.setAlignment(Qt.AlignCenter)

        val_lbl = QLabel(value)
        val_lbl.setAlignment(Qt.AlignCenter)
        val_lbl.setStyleSheet("font-size: 26px; font-weight: bold; color: #eeeef5;")
        lay.addWidget(val_lbl)

        lbl_lbl = QLabel(label)
        lbl_lbl.setAlignment(Qt.AlignCenter)
        lbl_lbl.setStyleSheet("font-size: 10px; color: #444; letter-spacing: 0.5px;")
        lay.addWidget(lbl_lbl)

        card._val_lbl = val_lbl
        return card

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget()

        # ── Подписки ──────────────────────────────────────────────────────────
        subs_tab = QWidget()
        st_lay = QVBoxLayout(subs_tab)
        st_lay.setContentsMargins(0, 12, 0, 0)
        st_lay.setSpacing(10)

        self._subs_container = QVBoxLayout()
        self._subs_container.setSpacing(10)
        self._no_subs = QLabel("Нет активных подписок")
        self._no_subs.setAlignment(Qt.AlignCenter)
        self._no_subs.setStyleSheet("color: #444; font-size: 13px; padding: 20px;")
        self._subs_container.addWidget(self._no_subs)
        st_lay.addLayout(self._subs_container)
        st_lay.addStretch()
        tabs.addTab(subs_tab, "Подписки")

        # ── История платежей ──────────────────────────────────────────────────
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

        # ── Персонализация ────────────────────────────────────────────────────
        tabs.addTab(self._build_personalization_tab(), "Персонализация")

        return tabs

    def _build_personalization_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 16, 0, 0)
        lay.setSpacing(16)

        # Avatar card
        av_card = QFrame()
        av_card.setProperty("class", "card")
        av_lay = QVBoxLayout(av_card)
        av_lay.setContentsMargins(18, 14, 18, 14)
        av_lay.setSpacing(10)

        sec_lbl = QLabel("АВАТАР")
        sec_lbl.setStyleSheet(
            "color: #5a2020; font-size: 10px; font-weight: bold; letter-spacing: 2px;"
        )
        av_lay.addWidget(sec_lbl)
        av_lay.addWidget(_sep())

        hint = QLabel("Выберите иконку профиля — отображается в шапке кабинета")
        hint.setStyleSheet("color: #3a1a1a; font-size: 11px;")
        av_lay.addWidget(hint)

        cur_av = self._prefs.get("avatar_emoji", "👤")
        self._av_btns: list[QPushButton] = []
        grid = QGridLayout()
        grid.setSpacing(8)

        _emoji_font = QFont()
        _emoji_font.setFamilies(["Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", "Segoe UI Symbol"])
        _emoji_font.setPointSize(18)

        def _av_style(active: bool) -> str:
            base = "padding: 0; font-size: 20px; color: #ffffff;"
            if active:
                return (
                    f"QPushButton {{ {base}"
                    "background: rgba(185,22,22,60);"
                    "border: 2px solid rgba(255,70,70,200);"
                    "border-radius: 10px; }"
                    "QPushButton:hover { background: rgba(185,22,22,100); }"
                    "QPushButton:pressed { background: rgba(60,5,5,200);"
                    "border: 1px solid rgba(120,10,10,180); }"
                )
            return (
                f"QPushButton {{ {base}"
                "background: rgba(20,6,6,140);"
                "border: 1px solid rgba(100,20,20,60);"
                "border-radius: 10px; }"
                "QPushButton:hover { background: rgba(185,22,22,30);"
                "border: 1px solid rgba(185,22,22,120); }"
                "QPushButton:pressed { background: rgba(60,5,5,120);"
                "border: 1px solid rgba(100,10,10,100); }"
            )

        for i, emoji in enumerate(AVATAR_EMOJIS):
            btn = QPushButton(emoji)
            btn.setFixedSize(44, 44)
            btn.setFont(_emoji_font)
            btn.setStyleSheet(_av_style(emoji == cur_av))
            self._av_btns.append(btn)
            grid.addWidget(btn, i // 8, i % 8)

        def _pick(emoji: str):
            _save_prefs({"avatar_emoji": emoji})
            self._prefs["avatar_emoji"] = emoji
            self._avatar_lbl.setText(emoji)
            for em, ab in zip(AVATAR_EMOJIS, self._av_btns):
                ab.setStyleSheet(_av_style(em == emoji))
                ab.setFont(_emoji_font)

        for emoji, btn in zip(AVATAR_EMOJIS, self._av_btns):
            btn.clicked.connect(lambda _=False, e=emoji: _pick(e))

        av_lay.addLayout(grid)
        lay.addWidget(av_card)

        # Nickname card
        nick_card = QFrame()
        nick_card.setProperty("class", "card")
        nick_lay = QVBoxLayout(nick_card)
        nick_lay.setContentsMargins(18, 14, 18, 14)
        nick_lay.setSpacing(10)

        sec2 = QLabel("ОТОБРАЖАЕМОЕ ИМЯ")
        sec2.setStyleSheet(
            "color: #5a2020; font-size: 10px; font-weight: bold; letter-spacing: 2px;"
        )
        nick_lay.addWidget(sec2)
        nick_lay.addWidget(_sep())

        nick_row = QHBoxLayout()
        nick_row.setSpacing(8)
        self._nick_edit = QLineEdit()
        self._nick_edit.setPlaceholderText("Оставьте пустым — используется имя из email")
        self._nick_edit.setText(self._prefs.get("display_name", ""))
        self._nick_edit.setFixedHeight(36)
        nick_save_btn = QPushButton("Сохранить")
        nick_save_btn.setFixedSize(130, 36)
        nick_row.addWidget(self._nick_edit)
        nick_row.addWidget(nick_save_btn)
        nick_lay.addLayout(nick_row)

        hint2 = QLabel(
            "При пустом поле используется имя до «@» в вашем email."
        )
        hint2.setWordWrap(True)
        hint2.setStyleSheet("color: #3a1a1a; font-size: 11px;")
        nick_lay.addWidget(hint2)
        lay.addWidget(nick_card)

        def _save_nick():
            val = self._nick_edit.text().strip()
            _save_prefs({"display_name": val})
            self._prefs["display_name"] = val
            user = self._auth.user or {}
            email = user.get("email", "—")
            self._display_name_lbl.setText(val or email.split("@")[0])
            nick_save_btn.setText("✓  Сохранено")
            QTimer.singleShot(1800, lambda: nick_save_btn.setText("Сохранить"))
            # Синхронизируем в vx_profiles (фоновый поток)
            web_user_id = user.get("id")
            if web_user_id and self._auth.access_token:
                vxp.set_display_name_async(
                    self._auth.access_token, web_user_id, val
                )

        nick_save_btn.clicked.connect(_save_nick)
        self._nick_edit.returnPressed.connect(_save_nick)

        lay.addStretch()
        return tab

    # ── Data ──────────────────────────────────────────────────────────────────

    def preload(self, token: str):
        self.load()

    def load(self):
        self._status_lbl.setText("Загрузка...")
        self._worker = _DataWorker(self._auth.access_token)
        self._worker.done.connect(self._on_loaded)
        self._worker.error.connect(lambda e: self._status_lbl.setText(f"Ошибка: {e}"))
        self._worker.start()
        # Синхронизируем профиль с vx_profiles в фоне
        self._sync_vx_profile()

    def _sync_vx_profile(self):
        """Upsert в vx_profiles в фоне; если там есть display_name — применяем к UI."""
        token = self._auth.access_token
        user  = self._auth.user or {}
        web_user_id = user.get("id")
        if not token or not web_user_id:
            return

        local_name = self._prefs.get("display_name") or None

        def _on_synced(profile):
            if not profile:
                return
            remote_name = profile.get("display_name")
            if remote_name and remote_name != self._prefs.get("display_name"):
                # Удалённое имя приоритетнее локального — применяем
                _save_prefs({"display_name": remote_name})
                self._prefs["display_name"] = remote_name
                try:
                    self._display_name_lbl.setText(remote_name)
                    self._nick_edit.setText(remote_name)
                except RuntimeError:
                    pass

        vxp.upsert_platform_profile_async(
            token, web_user_id,
            display_name=local_name,
            callback=_on_synced,
        )

    def _on_loaded(self, subs: list, payments: list):
        self._fill_subs(subs)
        self._fill_payments(payments)
        self._update_stats(subs)
        self._status_lbl.setText("")

    def _update_stats(self, subs: list):
        active = [s for s in subs if s.get("status") == "active"]
        self._stat_subs._val_lbl.setText(str(len(active)))
        if active:
            min_days = min(_days_left(s["expires_at"]) for s in active)
            self._stat_days._val_lbl.setText(str(min_days))
        else:
            self._stat_days._val_lbl.setText("—")

    def _fill_subs(self, subs: list):
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
            self._subs_container.addWidget(self._make_sub_card(sub))

    def _make_sub_card(self, sub: dict) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        tool_name = sub.get("tools", {}).get("name", "—")
        plan_name = sub.get("plans", {}).get("name", "—")
        expires = sub.get("expires_at", "")
        days = _days_left(expires)
        duration = sub.get("plans", {}).get("duration_days", 30)
        active = sub.get("status") == "active"

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

        plan_lbl = QLabel(
            f"Тариф: {plan_name}   •   Истекает: {_fmt_dt(expires) if expires else '—'}"
        )
        plan_lbl.setStyleSheet("color: #555; font-size: 11px;")
        lay.addWidget(plan_lbl)

        if active and duration > 0:
            bar = QProgressBar()
            bar.setRange(0, duration)
            bar.setValue(min(days, duration))
            bar.setFormat(f"  {days} дн. осталось")
            bar.setFixedHeight(16)
            lay.addWidget(bar)

        return card

    def _fill_payments(self, payments: list):
        self._pay_table.setRowCount(len(payments))
        for i, p in enumerate(payments):
            date   = _fmt_dt(p.get("paid_at") or p.get("created_at", ""))
            tool   = p.get("tool_name") or p.get("tool_id") or "—"
            plan   = p.get("plan_name") or p.get("plan_id") or "—"
            amount = f"{p.get('amount_rub', p.get('amount', 0))} ₽"
            for col, val in enumerate([date, tool, plan, amount]):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                self._pay_table.setItem(i, col, item)
