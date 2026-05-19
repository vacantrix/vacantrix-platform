from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QPoint, QRect, QTimer
from PySide6.QtGui import QPixmap, QCursor, QPainter, QColor, QBrush, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QSizePolicy, QScrollArea,
)

from launcher.core.auth_manager import AuthManager
from launcher.core import supabase_api as api
from launcher.core import cache as disk_cache
from launcher.core.downloader import needs_update, is_downloaded
from launcher.widgets.tool_card import TOOL_ICONS

DISPLAY_NAMES = {"vacantrix": "VACANTRIX-HH.ru"}

PANEL_H  = 280
PANEL_W  = 230
BANNER_H = 130
SB_W     = 12   # scrollbar width


def _days_left(expires_at: str) -> int:
    dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    return max(0, (dt - datetime.now(tz=timezone.utc)).days)


# ── Custom scrollbar ──────────────────────────────────────────────────────────

class _ScrollBar(QWidget):
    """Thin custom scrollbar drawn directly via QPainter. Supports drag."""

    scrolled = Signal(float)   # 0.0 – 1.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(SB_W)
        self.setCursor(Qt.ArrowCursor)
        self._ratio    = 1.0   # thumb_h / track_h
        self._pos      = 0.0   # 0.0 – 1.0
        self._dragging = False
        self._drag_y   = 0
        self._drag_p0  = 0.0

    # ── Public ────────────────────────────────────────────────────────────────

    def update_state(self, value: int, maximum: int, page_step: int):
        total = maximum + page_step
        self._ratio = page_step / total if total > 0 else 1.0
        self._pos   = value / maximum if maximum > 0 else 0.0
        self.update()

    # ── Thumb geometry ────────────────────────────────────────────────────────

    def _thumb_rect(self) -> QRect:
        h        = self.height()
        thumb_h  = max(28, int(h * self._ratio))
        max_top  = h - thumb_h
        top      = int(max_top * self._pos)
        return QRect(2, top, self.width() - 4, thumb_h)

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Track
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(8, 2, 2, 160)))
        p.drawRoundedRect(0, 0, self.width(), self.height(), 3, 3)

        # Thumb
        r = self._thumb_rect()
        if self._dragging:
            color = QColor(220, 40, 40, 230)
        else:
            color = QColor(180, 22, 22, 190)
        p.setBrush(QBrush(color))
        p.drawRoundedRect(r, 3, 3)

        p.end()

    # ── Mouse events ──────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            r = self._thumb_rect()
            if r.contains(e.pos()):
                self._dragging = True
                self._drag_y   = e.pos().y()
                self._drag_p0  = self._pos
                self.setCursor(Qt.ClosedHandCursor)
            else:
                # Jump to clicked position
                h       = self.height()
                thumb_h = max(28, int(h * self._ratio))
                max_top = h - thumb_h
                if max_top > 0:
                    new_pos = max(0.0, min(1.0,
                                  (e.pos().y() - thumb_h / 2) / max_top))
                    self._pos = new_pos
                    self.update()
                    self.scrolled.emit(self._pos)

    def mouseMoveEvent(self, e):
        if self._dragging:
            h       = self.height()
            thumb_h = max(28, int(h * self._ratio))
            max_top = h - thumb_h
            if max_top > 0:
                dy      = e.pos().y() - self._drag_y
                new_pos = max(0.0, min(1.0, self._drag_p0 + dy / max_top))
                self._pos = new_pos
                self.update()
                self.scrolled.emit(self._pos)
        else:
            r = self._thumb_rect()
            self.setCursor(
                Qt.OpenHandCursor if r.contains(e.pos()) else Qt.ArrowCursor
            )

    def mouseReleaseEvent(self, e):
        if self._dragging:
            self._dragging = False
            self.setCursor(Qt.ArrowCursor)
            self.update()


# ── Scroll area (native scrollbars hidden) ────────────────────────────────────

class _Col(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)
        self.setStyleSheet("background: transparent; border: none;")

    def wheelEvent(self, e):
        e.ignore()   # bubble up to CatalogScreen


# ── Worker ────────────────────────────────────────────────────────────────────

class _LoadWorker(QThread):
    done  = Signal(list, list)
    error = Signal(str)

    def __init__(self, token: str):
        super().__init__()
        self._token = token

    def run(self):
        try:
            tools = api.get_tools()
            subs  = api.get_subscriptions(self._token)
            self.done.emit(tools, subs)
        except Exception as e:
            self.error.emit(str(e))


# ── Catalog screen ────────────────────────────────────────────────────────────

class CatalogScreen(QWidget):
    logout_requested  = Signal()
    buy_requested     = Signal(dict)
    launch_requested  = Signal(dict)
    cabinet_requested = Signal()
    tool_selected     = Signal(dict, object)

    def __init__(self, auth: AuthManager, parent=None):
        super().__init__(parent)
        self._auth    = auth
        self._worker  = None
        self._loaded  = False
        self._on_done = None
        self._build()

    # ── Public ────────────────────────────────────────────────────────────────

    def load_once(self, on_done=None, force: bool = False):
        self._on_done = on_done
        if self._loaded and not force:
            if on_done:
                on_done([], [])
            return
        cached = disk_cache.load()
        if cached and not force:
            tools, subs = cached
            self._render(tools, subs, from_cache=True)
        self._fetch()

    def load(self):
        self._loaded = False
        self._status_lbl.setText("Обновление...")
        self._fetch()

    def refresh_download_state(self):
        """Перерисовывает карточки из кеша — обновляет кнопки после скачивания."""
        cached = disk_cache.load()
        if cached:
            tools, subs = cached
            self._render(tools, subs, from_cache=True)

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        header = QFrame()
        header.setProperty("class", "header")
        header.setFixedHeight(52)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 0, 28, 0)   # 28 right = leave room for scrollbar
        h_lay.setSpacing(8)

        logo = QLabel("Vacantrix Platform")
        logo.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #eeeef5; letter-spacing: 0.5px;"
        )
        h_lay.addWidget(logo)
        h_lay.addStretch()

        user = self._auth.user or {}
        self._email_lbl = QLabel(user.get("email", ""))
        self._email_lbl.setStyleSheet("color: #555; font-size: 11px;")
        h_lay.addWidget(self._email_lbl)

        cabinet_btn = QPushButton("Кабинет")
        cabinet_btn.setFixedHeight(30)
        cabinet_btn.clicked.connect(self.cabinet_requested)
        h_lay.addWidget(cabinet_btn)

        logout_btn = QPushButton("Выйти")
        logout_btn.setProperty("class", "danger")
        logout_btn.setFixedHeight(30)
        logout_btn.clicked.connect(self.logout_requested)
        h_lay.addWidget(logout_btn)

        root.addWidget(header)

        # ── Mid: left column | transparent center | right column ──────────────
        mid = QWidget()
        mid.setStyleSheet("background: transparent;")
        mid_lay = QHBoxLayout(mid)
        mid_lay.setContentsMargins(0, 0, SB_W + 2, 0)   # right gap for scrollbar
        mid_lay.setSpacing(0)

        # Left column
        self._left_scroll = _Col()
        self._left_scroll.setFixedWidth(PANEL_W + 24)
        lc = QWidget()
        lc.setStyleSheet("background: transparent;")
        self._left_vlay = QVBoxLayout(lc)
        self._left_vlay.setContentsMargins(12, 16, 6, 16)
        self._left_vlay.setSpacing(12)
        self._left_vlay.setAlignment(Qt.AlignTop)
        self._left_scroll.setWidget(lc)
        mid_lay.addWidget(self._left_scroll)

        # Transparent center (GIF shows through)
        center = QWidget()
        center.setStyleSheet("background: transparent;")
        center.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        mid_lay.addWidget(center, stretch=1)

        # Right column
        self._right_scroll = _Col()
        self._right_scroll.setFixedWidth(PANEL_W + 24)
        rc = QWidget()
        rc.setStyleSheet("background: transparent;")
        self._right_vlay = QVBoxLayout(rc)
        self._right_vlay.setContentsMargins(6, 16, 12, 16)
        self._right_vlay.setSpacing(12)
        self._right_vlay.setAlignment(Qt.AlignTop)
        self._right_scroll.setWidget(rc)
        mid_lay.addWidget(self._right_scroll)

        root.addWidget(mid, stretch=1)

        # Footer
        footer = QFrame()
        footer.setProperty("class", "footer")
        footer.setFixedHeight(50)
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(20, 8, SB_W + 10, 8)
        f_lay.setSpacing(8)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color: #444; font-size: 11px;")
        f_lay.addWidget(self._status_lbl)
        f_lay.addStretch()

        refresh = QPushButton("⟳  Обновить")
        refresh.setFixedHeight(34)
        refresh.setFixedWidth(120)
        refresh.clicked.connect(self.load)
        f_lay.addWidget(refresh)
        root.addWidget(footer)

        # ── Custom scrollbar overlay (full height, right edge) ─────────────────
        self._sb = _ScrollBar(self)
        self._sb.scrolled.connect(self._on_sb_dragged)
        self._sb.raise_()

        # Sync native scrollbar → custom scrollbar
        self._left_scroll.verticalScrollBar().valueChanged.connect(
            self._sync_sb
        )

        # Pre-fill placeholders
        for _ in range(4):
            self._left_vlay.addWidget(self._make_placeholder())
            self._right_vlay.addWidget(self._make_placeholder())

        QTimer.singleShot(0, self._sync_sb)

    # ── Resize — keep scrollbar pinned to right edge, full height ─────────────

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._sb.setGeometry(self.width() - SB_W, 0, SB_W, self.height())
        self._sb.raise_()

    # ── Wheel — scroll both columns together ──────────────────────────────────

    def wheelEvent(self, e):
        step = -e.angleDelta().y() // 2
        lsb = self._left_scroll.verticalScrollBar()
        rsb = self._right_scroll.verticalScrollBar()
        lsb.setValue(lsb.value() + step)
        rsb.setValue(rsb.value() + step)
        self._sync_sb()
        e.accept()

    # ── Scrollbar sync ────────────────────────────────────────────────────────

    def _sync_sb(self):
        sb = self._left_scroll.verticalScrollBar()
        self._sb.update_state(sb.value(), sb.maximum(), sb.pageStep())

    def _on_sb_dragged(self, pos: float):
        lsb = self._left_scroll.verticalScrollBar()
        rsb = self._right_scroll.verticalScrollBar()
        lsb.setValue(int(pos * lsb.maximum()))
        rsb.setValue(int(pos * rsb.maximum()))

    # ── Data ──────────────────────────────────────────────────────────────────

    def _fetch(self):
        if self._worker and self._worker.isRunning():
            return
        self._worker = _LoadWorker(self._auth.access_token)
        self._worker.done.connect(self._on_fetched)
        self._worker.error.connect(lambda e: self._status_lbl.setText(f"Ошибка: {e}"))
        self._worker.start()

    def _on_fetched(self, tools: list, subs: list):
        disk_cache.save(tools, subs)
        self._loaded = True
        self._render(tools, subs, from_cache=False)
        if self._on_done:
            self._on_done(tools, subs)
            self._on_done = None

    def _clear_col(self, vlay: QVBoxLayout):
        while vlay.count():
            item = vlay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _render(self, tools: list, subs: list, from_cache: bool = False):
        self._clear_col(self._left_vlay)
        self._clear_col(self._right_vlay)

        sub_by_tool = {s["tool_id"]: s for s in subs}
        slots = [(self._left_vlay,)] * 4 + [(self._right_vlay,)] * 4

        for i, (vlay,) in enumerate(slots):
            if i < len(tools):
                tool   = tools[i]
                sub    = sub_by_tool.get(tool["id"])
                widget = self._make_product_panel(tool, sub)
            else:
                widget = self._make_placeholder()
            vlay.addWidget(widget)

        QTimer.singleShot(50, self._sync_sb)

        suffix = " (кеш)" if from_cache else ""
        self._status_lbl.setText(f"Инструментов: {len(tools)}{suffix}")

    # ── Panel builders ────────────────────────────────────────────────────────

    def _make_product_panel(self, tool: dict, sub) -> QFrame:
        slug  = tool.get("slug", "")
        panel = QFrame()
        panel.setProperty("class", "card")
        panel.setFixedSize(PANEL_W, PANEL_H)
        panel.setCursor(QCursor(Qt.PointingHandCursor))

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 14)
        lay.setSpacing(0)

        banner = QLabel()
        banner.setFixedHeight(BANNER_H)
        banner.setAlignment(Qt.AlignCenter)
        banner.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 rgba(40,5,5,255), stop:1 rgba(15,2,2,255));"
            "border-radius: 12px 12px 0 0;"
        )
        icon_path = TOOL_ICONS.get(slug)
        if icon_path and Path(icon_path).exists():
            px = QPixmap(icon_path).scaled(
                100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            banner.setPixmap(px)
        else:
            banner.setText(tool.get("icon_url") or "🔧")
            banner.setStyleSheet(banner.styleSheet() + " font-size: 48px;")
        lay.addWidget(banner)

        info = QVBoxLayout()
        info.setContentsMargins(14, 10, 14, 0)
        info.setSpacing(5)

        display_name = DISPLAY_NAMES.get(slug, tool["name"])
        name_lbl = QLabel(display_name)
        name_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #eeeef5;")
        name_lbl.setWordWrap(True)
        info.addWidget(name_lbl)

        tagline = QLabel(tool.get("tagline") or "")
        tagline.setStyleSheet("color: #666; font-size: 10px;")
        tagline.setWordWrap(True)
        info.addWidget(tagline)

        info.addStretch()

        status = tool.get("status", "active")
        if status == "coming_soon":
            st = QLabel("🚧 В разработке")
            st.setStyleSheet("color: #666; font-size: 10px;")
            info.addWidget(st)
            btn = QPushButton("Скоро")
            btn.setEnabled(False)
            btn.setFixedHeight(34)
            info.addWidget(btn)
        elif sub and sub.get("status") == "active":
            days = _days_left(sub["expires_at"])
            st = QLabel(f"✅  Активна: {days} дн.")
            st.setStyleSheet("color: #4caf50; font-size: 10px; font-weight: bold;")
            info.addWidget(st)
            name_val   = tool.get("name", "")
            downloaded = is_downloaded(slug, name_val)
            outdated   = needs_update(slug, tool.get("version", ""))
            if not downloaded:
                btn_text = "⬇  Скачать"
            elif outdated:
                btn_text = "🔄  Обновить"
            else:
                btn_text = "▶  Запустить"
            btn = QPushButton(btn_text)
            btn.setFixedHeight(34)
            btn.clicked.connect(
                lambda checked=False, t=tool: self.launch_requested.emit(t)
            )
            info.addWidget(btn)
        else:
            st = QLabel("🔒  Нет подписки")
            st.setStyleSheet("color: #c41c1c; font-size: 10px; font-weight: bold;")
            info.addWidget(st)
            btn = QPushButton("Купить подписку")
            btn.setFixedHeight(34)
            btn.clicked.connect(
                lambda checked=False, t=tool: self.buy_requested.emit(t)
            )
            info.addWidget(btn)

        lay.addLayout(info)

        def _on_press(e, t=tool, s=sub):
            if e.button() == Qt.LeftButton:
                self.tool_selected.emit(t, s)

        panel.mousePressEvent = _on_press
        return panel

    def _make_placeholder(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("class", "card")
        panel.setFixedSize(PANEL_W, PANEL_H)

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 14)
        lay.setSpacing(0)

        banner = QLabel("🔧")
        banner.setFixedHeight(BANNER_H)
        banner.setAlignment(Qt.AlignCenter)
        banner.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 rgba(28,4,4,255), stop:1 rgba(10,1,1,255));"
            "border-radius: 12px 12px 0 0; font-size: 48px; color: #200808;"
        )
        lay.addWidget(banner)

        info = QVBoxLayout()
        info.setContentsMargins(14, 10, 14, 0)
        info.setSpacing(5)

        name_lbl = QLabel("Скоро")
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #2e0a0a;")
        info.addWidget(name_lbl)

        badge = QLabel("🚧 В разработке")
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet("color: #250808; font-size: 10px;")
        info.addWidget(badge)

        info.addStretch()

        btn = QPushButton("Скоро")
        btn.setEnabled(False)
        btn.setFixedHeight(34)
        info.addWidget(btn)

        lay.addLayout(info)
        return panel
