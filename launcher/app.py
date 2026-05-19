import sys
from pathlib import Path

from PySide6.QtCore import Qt, QPoint, QSize, QTimer
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QMovie
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QMessageBox, QFrame,
)

from launcher.core.auth_manager import AuthManager
from launcher.core.downloader import needs_update, launch
from launcher.core import cache as disk_cache
from launcher.screens.auth_screen import AuthScreen
from launcher.screens.catalog_screen import CatalogScreen
from launcher.screens.cabinet_screen import CabinetScreen
from launcher.screens.tool_detail_screen import ToolDetailScreen
from launcher.widgets.payment_modal import PaymentModal
from launcher.widgets.download_dialog import DownloadDialog
from launcher.widgets.toast import show_toast

RESOURCES     = Path(__file__).parent.parent / "resources"
ICON_PATH     = RESOURCES / "vacantrix_icon.png"
GIF_PATH      = RESOURCES / "background.gif"
BTN_CLOSE_IMG = RESOURCES / "btn_close.png"
BTN_MAX_IMG   = RESOURCES / "btn_maximize.png"
BTN_MIN_IMG   = RESOURCES / "btn_minimize.png"


# ── GIF background ────────────────────────────────────────────────────────────

class _GifBg(QWidget):
    """
    Lightweight animated GIF background via QMovie.
    Each frame is downscaled to a thumbnail to keep paint time minimal.
    Renders BEHIND all child widgets (just a paintEvent).
    """

    _THUMB_W = 854
    _THUMB_H = 480

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._frame_px   = QPixmap()
        self._icon_px    = QPixmap(str(ICON_PATH)) if ICON_PATH.exists() else QPixmap()
        self._icon_cache: QPixmap | None = None
        self._icon_size  = -1

        self._movie = QMovie(str(GIF_PATH))
        self._movie.frameChanged.connect(self._on_frame)
        if GIF_PATH.exists():
            self._movie.start()

    def _on_frame(self, _frame_number: int):
        px = self._movie.currentPixmap()
        if px.isNull():
            return
        self._frame_px = px.scaled(
            self._THUMB_W, self._THUMB_H,
            Qt.KeepAspectRatio, Qt.FastTransformation,
        )
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        # 1. Dark base
        p.fillRect(self.rect(), QColor(7, 3, 3))

        # 2. GIF frame — уменьшен до 55% окна, центрирован (эффект отдалённости)
        if not self._frame_px.isNull():
            scaled = self._frame_px.scaled(
                int(self.width() * 0.55), int(self.height() * 0.55),
                Qt.KeepAspectRatio,
                Qt.FastTransformation,
            )
            x = (self.width()  - scaled.width())  // 2
            y = (self.height() - scaled.height()) // 2
            p.setOpacity(0.58)
            p.drawPixmap(x, y, scaled)

        # 3. Dark overlay — keeps UI readable
        p.setOpacity(0.45)
        p.fillRect(self.rect(), QColor(4, 0, 0))

        # 4. Icon watermark (cache scaled version)
        if not self._icon_px.isNull():
            size = int(min(self.width(), self.height()) * 0.50)
            if size != self._icon_size:
                self._icon_cache = self._icon_px.scaled(
                    size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self._icon_size = size
            ix = (self.width()  - self._icon_cache.width())  // 2
            iy = (self.height() - self._icon_cache.height()) // 2
            p.setOpacity(0.07)
            p.drawPixmap(ix, iy, self._icon_cache)

        p.end()


# ── Title bar ─────────────────────────────────────────────────────────────────

class _TitleBar(QFrame):
    def __init__(self, window: QMainWindow, parent=None):
        super().__init__(parent)
        self._win      = window
        self._drag_pos = QPoint()
        self.setFixedHeight(46)
        self.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 rgba(10,2,2,220),
                    stop:0.5 rgba(18,4,4,210),
                    stop:1 rgba(10,2,2,220));
                border-bottom: 1px solid rgba(200,25,25,90);
                border-radius: 14px 14px 0 0;
            }
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 12, 0)
        lay.setSpacing(0)

        # Icon left
        if ICON_PATH.exists():
            icon_lbl = QLabel()
            px = QPixmap(str(ICON_PATH)).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_lbl.setPixmap(px)
            lay.addWidget(icon_lbl)
            lay.addSpacing(8)

        # Title
        title = QLabel("Vacantrix Platform")
        title.setStyleSheet(
            "color: rgba(200,90,90,160); font-size: 12px; font-weight: bold; letter-spacing: 1.2px;"
        )
        lay.addWidget(title)
        lay.addStretch()

        # ── Window controls RIGHT ─────────────────────────────────────────────
        _ICON_SIZE = QSize(36, 36)

        def _wbtn(img_path, tooltip, slot, hover_bg):
            btn = QPushButton()
            btn.setToolTip(tooltip)
            btn.setFixedSize(38, 38)
            btn.setIconSize(_ICON_SIZE)
            btn.setContentsMargins(0, 0, 0, 0)
            if img_path.exists():
                btn.setIcon(QIcon(str(img_path)))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    padding: 0px;
                }}
                QPushButton:hover {{
                    background: {hover_bg};
                    border-radius: 5px;
                }}
                QPushButton:pressed {{
                    background: rgba(200,25,25,160);
                    border-radius: 5px;
                }}
            """)
            btn.clicked.connect(slot)
            return btn

        lay.addWidget(_wbtn(BTN_MIN_IMG, "Свернуть",   window.showMinimized, "rgba(160,160,160,50)"))
        lay.addWidget(_wbtn(BTN_MAX_IMG, "Развернуть", self._toggle_max,     "rgba(200,60,60,70)"))
        lay.addWidget(_wbtn(BTN_CLOSE_IMG, "Закрыть",  window.close,         "rgba(220,30,30,130)"))

    def _toggle_max(self):
        if self._win.isMaximized():
            self._win.showNormal()
        else:
            self._win.showMaximized()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self._win.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton and not self._drag_pos.isNull():
            self._win.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = QPoint()

    def mouseDoubleClickEvent(self, e):
        self._toggle_max()


# ── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vacantrix Platform")
        self.setMinimumSize(960, 660)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        self._auth = AuthManager()

        # Root container
        root = QWidget()
        root.setObjectName("root")
        root.setStyleSheet("#root { background: transparent; border: 1px solid rgba(180,20,20,70); border-radius: 14px; }")
        self.setCentralWidget(root)

        root_lay = QVBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # GIF BG — absolute, behind everything
        self._bg = _GifBg(root)
        self._bg.setGeometry(root.rect())
        self._bg.lower()
        root.resizeEvent = lambda e: self._bg.setGeometry(root.rect())

        # Title bar
        self._title_bar = _TitleBar(self, root)
        root_lay.addWidget(self._title_bar)

        # Screens
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")
        root_lay.addWidget(self._stack, stretch=1)

        self._auth_screen = AuthScreen(self._auth)
        self._auth_screen.logged_in.connect(self._on_logged_in)
        self._stack.addWidget(self._auth_screen)          # 0

        self._catalog = CatalogScreen(self._auth)
        self._catalog.logout_requested.connect(self._on_logout)
        self._catalog.buy_requested.connect(self._on_buy)
        self._catalog.launch_requested.connect(self._on_launch)
        self._catalog.cabinet_requested.connect(lambda: self._go(2))
        self._catalog.tool_selected.connect(self._show_detail)
        self._stack.addWidget(self._catalog)              # 1

        self._cabinet = CabinetScreen(self._auth)
        self._cabinet.back_requested.connect(lambda: self._go(1))
        self._stack.addWidget(self._cabinet)              # 2

        self._detail = ToolDetailScreen(self._auth)
        self._detail.back_requested.connect(lambda: self._go(1))
        self._detail.buy_requested.connect(self._on_buy)
        self._detail.launch_requested.connect(self._on_launch)
        self._detail.download_requested.connect(self._on_download)
        self._stack.addWidget(self._detail)               # 3

        self._restore_session()

    def _go(self, idx: int):
        self._stack.setCurrentIndex(idx)

    def _restore_session(self):
        if self._auth.restore_session():
            self._preload_and_show()
        else:
            self._go(0)

    def _preload_and_show(self):
        self._catalog.load_once(on_done=self._on_data_ready, force=True)
        self._go(1)
        self._start_update_timer()

    def _start_update_timer(self):
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(15 * 60 * 1000)  # каждые 15 минут
        self._update_timer.timeout.connect(self._silent_update_check)
        self._update_timer.start()

    def _silent_update_check(self):
        """Фоновая проверка обновлений без сброса текущего вида каталога."""
        if self._auth.is_logged_in():
            self._catalog.load_once(force=True)

    def _on_data_ready(self, tools, subs):
        self._cabinet.preload(self._auth.access_token)

    def _on_logged_in(self):
        self._preload_and_show()

    def _show_detail(self, tool, sub):
        self._detail.load(tool, sub)
        self._go(3)

    def _on_logout(self):
        self._auth.sign_out()
        disk_cache.clear()
        self._go(0)

    def _on_buy(self, tool):
        modal = PaymentModal(tool, self._auth, parent=self)
        modal.payment_done.connect(lambda: self._catalog.load_once(force=True))
        modal.payment_done.connect(
            lambda: show_toast(f"✅ Подписка на {tool['name']} активирована!", self)
        )
        modal.exec()

    def _on_launch(self, tool):
        if needs_update(tool["slug"], tool.get("version", "")):
            dlg = DownloadDialog(tool, parent=self)
            if dlg.exec() != DownloadDialog.Accepted:
                return
            show_toast(f"✅ {tool['name']} обновлён", self)
            self._detail.refresh_status()
            self._catalog.refresh_download_state()
        if not launch(tool["slug"], tool["name"]):
            QMessageBox.warning(self, "Ошибка", f"Не удалось запустить {tool['name']}")
        else:
            show_toast(f"▶  {tool['name']} запущен", self)

    def _on_download(self, tool):
        dlg = DownloadDialog(tool, parent=self)
        if dlg.exec() == DownloadDialog.Accepted:
            show_toast(f"✅ {tool['name']} скачан!", self)
            self._detail.refresh_status()
            self._catalog.refresh_download_state()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            m = 8
            p = e.pos()
            r = self.rect()
            if p.x() > r.width() - m and p.y() > r.height() - m:
                self._resizing  = True
                self._res_start = e.globalPosition().toPoint()
                self._res_geo   = self.geometry()
                return
        self._resizing = False
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if getattr(self, "_resizing", False):
            d = e.globalPosition().toPoint() - self._res_start
            g = self._res_geo
            self.setGeometry(g.x(), g.y(), max(960, g.width()+d.x()), max(660, g.height()+d.y()))
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._resizing = False
        super().mouseReleaseEvent(e)
