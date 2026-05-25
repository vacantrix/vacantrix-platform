from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QMessageBox,
)

from PySide6.QtCore import QThread, Signal as QSignal
from launcher.core.auth_manager import AuthManager
from launcher.core.downloader import needs_update, is_downloaded, TOOLS_DIR
from launcher.core import supabase_api as api
from launcher.widgets.image_carousel import ImageCarousel
from launcher import theme

TRIAL_LIMIT = 10


class _TrialWorker(QThread):
    done = QSignal(int)

    def __init__(self, token: str, tool_id: str):
        super().__init__()
        self._token, self._tool_id = token, tool_id

    def run(self):
        try:
            self.done.emit(api.get_trial(self._token, self._tool_id))
        except Exception:
            self.done.emit(0)

from launcher.paths import RESOURCES as _RESOURCES

_LOCAL_SCREENSHOTS: dict[str, list[str]] = {
    "vacantrix": [
        str(_RESOURCES / "screenshots" / "01_main.png"),
        str(_RESOURCES / "screenshots" / "02_details.png"),
        str(_RESOURCES / "screenshots" / "03_stats.png"),
        str(_RESOURCES / "screenshots" / "04_settings.png"),
        str(_RESOURCES / "screenshots" / "05_hh.jpg"),
    ],
    "avito": [
        # Скриншоты Авито-бота — добавьте файлы в resources/screenshots/avito/
        p for p in [
            str(_RESOURCES / "screenshots" / "avito" / "01_main.png"),
            str(_RESOURCES / "screenshots" / "avito" / "02_settings.png"),
        ] if Path(p).exists()
    ],
}


def _days_left(expires_at: str) -> int:
    dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    return max(0, (dt - datetime.now(tz=timezone.utc)).days)


class ToolDetailScreen(QWidget):
    back_requested     = Signal()
    buy_requested      = Signal(dict)
    launch_requested   = Signal(dict)
    download_requested = Signal(dict)

    def __init__(self, auth: AuthManager, parent=None):
        super().__init__(parent)
        self._auth         = auth
        self._tool         = None
        self._sub          = None
        self._trial_used   = 0
        self._trial_worker = None
        self._build()

    # ── Build UI ──────────────────────────────────────────────────────────────

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

        self._header_title = QLabel("")
        self._header_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #eeeef5;")
        h_lay.addWidget(self._header_title)
        h_lay.addStretch()
        root.addWidget(header)

        # Body: scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        b_lay = QHBoxLayout(body)
        b_lay.setContentsMargins(24, 24, 24, 24)
        b_lay.setSpacing(24)
        b_lay.setAlignment(Qt.AlignTop)

        # LEFT — carousel + description
        left = QVBoxLayout()
        left.setSpacing(16)

        self._carousel = ImageCarousel([], parent=self)
        left.addWidget(self._carousel, stretch=1)

        desc_frame = QFrame()
        desc_frame.setProperty("class", "card")
        df_lay = QVBoxLayout(desc_frame)
        df_lay.setContentsMargins(16, 16, 16, 16)

        desc_title = QLabel("Описание")
        desc_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #eeeef5; letter-spacing: 0.5px;")
        df_lay.addWidget(desc_title)

        self._desc_label = QLabel("")
        self._desc_label.setWordWrap(True)
        self._desc_label.setStyleSheet("color: #aaa; font-size: 12px; line-height: 1.6;")
        df_lay.addWidget(self._desc_label)

        feat_title = QLabel("Возможности")
        feat_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #eeeef5; margin-top: 10px;")
        df_lay.addWidget(feat_title)

        self._feat_container = QVBoxLayout()
        self._feat_container.setSpacing(4)
        df_lay.addLayout(self._feat_container)

        left.addWidget(desc_frame)
        b_lay.addLayout(left, stretch=3)

        # RIGHT — sidebar
        sidebar = QFrame()
        sidebar.setProperty("class", "sidebar")
        sidebar.setFixedWidth(260)
        sb_lay = QVBoxLayout(sidebar)
        sb_lay.setContentsMargins(20, 24, 20, 24)
        sb_lay.setSpacing(12)
        sb_lay.setAlignment(Qt.AlignTop)

        self._tool_name_lbl = QLabel("")
        self._tool_name_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #eeeef5;")
        self._tool_name_lbl.setWordWrap(True)
        sb_lay.addWidget(self._tool_name_lbl)

        self._tagline_lbl = QLabel("")
        self._tagline_lbl.setStyleSheet("color: #888; font-size: 12px;")
        self._tagline_lbl.setWordWrap(True)
        sb_lay.addWidget(self._tagline_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: rgba(200,25,25,60);")
        sep.setFixedHeight(1)
        sb_lay.addWidget(sep)

        # Status block
        self._status_frame = QFrame()
        self._status_frame.setProperty("class", "card")
        sf_lay = QVBoxLayout(self._status_frame)
        sf_lay.setContentsMargins(12, 12, 12, 12)
        sf_lay.setSpacing(8)

        self._status_lbl = QLabel("")
        self._status_lbl.setAlignment(Qt.AlignCenter)
        sf_lay.addWidget(self._status_lbl)

        self._days_lbl = QLabel("")
        self._days_lbl.setAlignment(Qt.AlignCenter)
        self._days_lbl.setStyleSheet("color: #555; font-size: 11px;")
        sf_lay.addWidget(self._days_lbl)

        sb_lay.addWidget(self._status_frame)

        # ── Trial banner ────────────────────────────────────────────────────────
        self._trial_frame = QFrame()
        self._trial_frame.setProperty("class", "card")
        tf_lay = QVBoxLayout(self._trial_frame)
        tf_lay.setContentsMargins(12, 10, 12, 10)
        tf_lay.setSpacing(4)
        self._trial_lbl = QLabel("")
        self._trial_lbl.setAlignment(Qt.AlignCenter)
        self._trial_lbl.setStyleSheet("color: #ffd060; font-size: 12px; font-weight: bold;")
        tf_lay.addWidget(self._trial_lbl)
        self._trial_sub = QLabel("Пробный доступ — без подписки")
        self._trial_sub.setAlignment(Qt.AlignCenter)
        self._trial_sub.setStyleSheet("color: #666; font-size: 10px;")
        tf_lay.addWidget(self._trial_sub)
        self._trial_frame.hide()
        sb_lay.addWidget(self._trial_frame)

        # ── Action button (Launch / Download+Launch / Buy / Coming soon) ────────
        self._action_btn = QPushButton("")
        self._action_btn.setFixedHeight(46)
        self._action_btn.setProperty("class", "launch")
        theme.glow(self._action_btn, 24, 0.5)
        sb_lay.addWidget(self._action_btn)

        # ── Download button (⬇ Скачать — same launch style) ────────────────────
        self._download_btn = QPushButton("⬇  Скачать")
        self._download_btn.setFixedHeight(46)
        self._download_btn.setProperty("class", "launch")
        theme.glow(self._download_btn, 20, 0.4)
        self._download_btn.hide()
        sb_lay.addWidget(self._download_btn)

        # ── Delete sub-button ───────────────────────────────────────────────────
        self._delete_btn = QPushButton("🗑  Удалить")
        self._delete_btn.setFixedHeight(32)
        self._delete_btn.setProperty("class", "danger")
        self._delete_btn.hide()
        sb_lay.addWidget(self._delete_btn)

        sb_lay.addStretch()

        self._version_lbl = QLabel("")
        self._version_lbl.setAlignment(Qt.AlignCenter)
        self._version_lbl.setStyleSheet("color: #444; font-size: 11px;")
        sb_lay.addWidget(self._version_lbl)

        b_lay.addWidget(sidebar)
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

    # ── Public ────────────────────────────────────────────────────────────────

    def load(self, tool: dict, subscription: dict | None):
        self._tool       = tool
        self._sub        = subscription
        self._trial_used = 0
        # Загружаем счётчик пробных откликов в фоне
        if self._auth.access_token:
            self._trial_worker = _TrialWorker(self._auth.access_token, tool["id"])
            self._trial_worker.done.connect(self._on_trial_loaded)
            self._trial_worker.start()

        self._header_title.setText(tool.get("name", ""))
        self._tool_name_lbl.setText(tool.get("name", ""))
        self._tagline_lbl.setText(tool.get("tagline", ""))
        self._desc_label.setText(
            tool.get("description_full") or tool.get("tagline") or ""
        )
        version = tool.get("version", "")
        self._version_lbl.setText(f"версия {version}" if version else "")

        # Carousel
        old = self._carousel
        screenshots = tool.get("screenshots") or []
        if not screenshots:
            screenshots = _LOCAL_SCREENSHOTS.get(tool.get("slug", ""), [])
        new = ImageCarousel(
            screenshots, tool_name=tool.get("name", ""), parent=self
        )
        old.deleteLater()
        self._carousel = new
        layout = self.findChild(QScrollArea).widget().layout()
        layout.itemAt(0).layout().insertWidget(0, new, stretch=1)

        # Features
        while self._feat_container.count():
            item = self._feat_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for feat in tool.get("features") or []:
            row = QLabel(f"✓  {feat}")
            row.setStyleSheet("color: #cc3333; font-size: 12px;")
            self._feat_container.addWidget(row)

        self._update_status()

    def refresh_status(self):
        """Обновляет кнопки без перезагрузки данных — вызывается после скачивания."""
        if self._tool:
            self._update_status()

    def _on_trial_loaded(self, used: int):
        self._trial_used = used
        self._update_status()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _disconnect_all(self):
        for btn in (self._action_btn, self._download_btn, self._delete_btn):
            try:
                btn.clicked.disconnect()
            except Exception:
                pass

    def _update_status(self):
        self._disconnect_all()
        self._download_btn.hide()
        self._delete_btn.hide()
        self._action_btn.setEnabled(True)

        sub    = self._sub
        tool   = self._tool
        status = tool.get("status", "active")
        slug   = tool.get("slug", "")
        name   = tool.get("name", "")

        if status == "coming_soon":
            self._status_lbl.setText("🚧  В разработке")
            self._status_lbl.setStyleSheet("color: #888; font-size: 13px;")
            self._days_lbl.setText("")
            self._action_btn.setText("Скоро")
            self._action_btn.setEnabled(False)
            return

        downloaded = is_downloaded(slug, name)
        outdated   = needs_update(slug, tool.get("version", ""))

        if sub and sub.get("status") == "active":
            # ── Подписка активна ──────────────────────────────────────────────
            days = _days_left(sub["expires_at"])
            self._status_lbl.setText("✅  Подписка активна")
            self._status_lbl.setStyleSheet(
                "color: #4caf50; font-size: 13px; font-weight: bold;"
            )
            self._days_lbl.setText(f"Осталось {days} дней")

            if not downloaded:
                # Ещё не скачан
                self._action_btn.setText("⬇  Скачать и запустить")
                self._action_btn.clicked.connect(lambda: self.launch_requested.emit(tool))
            elif outdated:
                # Есть старая версия — только «Обновить», запустить нельзя
                self._action_btn.setText("🔄  Обновить и запустить")
                self._action_btn.clicked.connect(lambda: self.launch_requested.emit(tool))
                self._delete_btn.show()
                self._delete_btn.clicked.connect(self._confirm_delete)
            else:
                # Актуальная версия
                self._action_btn.setText("▶  Запустить")
                self._action_btn.clicked.connect(lambda: self.launch_requested.emit(tool))
                self._delete_btn.show()
                self._delete_btn.clicked.connect(self._confirm_delete)

        else:
            # ── Нет подписки ──────────────────────────────────────────────────
            trial_left = TRIAL_LIMIT - self._trial_used
            has_trial  = trial_left > 0

            if has_trial:
                self._status_lbl.setText("🎁  Пробный доступ")
                self._status_lbl.setStyleSheet("color: #ffd060; font-size: 13px; font-weight: bold;")
                self._days_lbl.setText(f"Осталось {trial_left} из {TRIAL_LIMIT} пробных откликов")
                self._trial_frame.show()
                self._trial_lbl.setText(f"🔓  {trial_left} / {TRIAL_LIMIT} откликов")
                self._action_btn.setText("Купить подписку")
                self._action_btn.clicked.connect(lambda: self.buy_requested.emit(tool))
            else:
                self._status_lbl.setText("🔒  Нет подписки")
                self._status_lbl.setStyleSheet("color: #c41c1c; font-size: 13px; font-weight: bold;")
                self._days_lbl.setText("Пробный лимит исчерпан")
                self._trial_frame.hide()
                self._action_btn.setText("Купить подписку")
                self._action_btn.clicked.connect(lambda: self.buy_requested.emit(tool))

            if not downloaded:
                if tool.get("download_url"):
                    self._download_btn.setText("⬇  Скачать")
                    self._download_btn.show()
                    self._download_btn.clicked.connect(
                        lambda: self.download_requested.emit(tool)
                    )
            elif outdated:
                self._download_btn.setText("🔄  Обновить")
                self._download_btn.show()
                self._download_btn.clicked.connect(
                    lambda: self.download_requested.emit(tool)
                )
                self._delete_btn.show()
                self._delete_btn.clicked.connect(self._confirm_delete)
            else:
                if has_trial:
                    self._download_btn.setText(f"▶  Запустить пробно ({trial_left})")
                    self._download_btn.show()
                    self._download_btn.clicked.connect(
                        lambda: self.launch_requested.emit(tool)
                    )
                    self._delete_btn.show()
                    self._delete_btn.clicked.connect(self._confirm_delete)
                else:
                    self._delete_btn.show()
                    self._delete_btn.clicked.connect(self._confirm_delete)

    def _confirm_delete(self):
        tool = self._tool
        reply = QMessageBox.question(
            self, "Удалить приложение",
            f"Удалить скачанный файл {tool['name']}.exe?\n"
            "Его можно будет скачать повторно.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._delete_tool()

    def _delete_tool(self):
        slug = self._tool["slug"]
        name = self._tool["name"]
        for fp in (
            TOOLS_DIR / slug / f"{name}.exe",
            TOOLS_DIR / slug / "version.txt",
        ):
            try:
                fp.unlink(missing_ok=True)
            except Exception:
                pass
        self._update_status()
