from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QLinearGradient, QPainterPath, QBrush, QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSizePolicy,
    QDialog, QLabel, QScrollArea,
)
import requests as _requests

_ANIM_MS     = 520
_INTERVAL_MS = 4500
_RADIUS      = 10
from launcher.paths import RESOURCES as _RES


# ── Загрузчик сетевых изображений ────────────────────────────────────────────

class _UrlLoader(QThread):
    loaded = Signal(int, QPixmap)

    def __init__(self, urls: list[str]):
        super().__init__()
        self._urls = urls

    def run(self):
        for i, url in enumerate(self._urls):
            try:
                data = _requests.get(url, timeout=10).content
                px = QPixmap()
                px.loadFromData(data)
                if not px.isNull():
                    self.loaded.emit(i, px)
            except Exception:
                pass


def _placeholder(text: str, w: int = 560, h: int = 320) -> QPixmap:
    px = QPixmap(w, h)
    px.fill(QColor(10, 4, 4))
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    grad = QLinearGradient(0, 0, w, h)
    grad.setColorAt(0, QColor(40, 8, 8, 200))
    grad.setColorAt(1, QColor(10, 2, 2, 240))
    p.fillRect(0, 0, w, h, grad)
    p.setPen(QColor(200, 25, 25, 80))
    for y in range(0, h, 30):
        p.drawLine(0, y, w, y)
    for x in range(0, w, 30):
        p.drawLine(x, 0, x, h)
    p.setPen(QColor(255, 68, 68, 200))
    p.setFont(QFont("Segoe UI", 14, QFont.Bold))
    p.drawText(px.rect(), Qt.AlignCenter, text)
    p.end()
    return px


# ── Лайтбокс ─────────────────────────────────────────────────────────────────

class _Lightbox(QDialog):
    """Полноэкранный просмотр фото с кнопками ← →."""

    def __init__(self, pixmaps: list[QPixmap], index: int, parent=None):
        super().__init__(parent)
        self._pixmaps = pixmaps
        self._index   = index
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setModal(True)
        self.setStyleSheet("background: rgba(0,0,0,220);")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Кнопка закрыть
        close_row = QHBoxLayout()
        close_row.setContentsMargins(16, 12, 16, 0)
        close_btn = QPushButton()
        close_btn.setFixedSize(36, 36)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; }"
            "QPushButton:hover { background: transparent; }"
        )
        close_path = _RES / "btn_close_custom.png"
        if close_path.exists():
            close_px = QPixmap(str(close_path)).scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            close_btn.setIcon(close_px)
            close_btn.setIconSize(close_px.size())
        close_btn.clicked.connect(self.close)
        close_row.addStretch()
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

        # Область с фото
        center = QHBoxLayout()
        center.setContentsMargins(20, 20, 20, 20)
        center.setSpacing(16)

        self._img_lbl = QLabel()
        self._img_lbl.setAlignment(Qt.AlignCenter)
        self._img_lbl.setStyleSheet("background: transparent;")

        arrow_style = (
            "QPushButton { background: transparent; border: none; }"
            "QPushButton:hover { background: transparent; }"
            "QPushButton:pressed { background: transparent; }"
        )

        left_btn  = self._make_arrow_btn("arrow_left.png",  arrow_style, 44)
        right_btn = self._make_arrow_btn("arrow_right.png", arrow_style, 44)
        left_btn.clicked.connect(self._prev)
        right_btn.clicked.connect(self._next)

        left_btn.setVisible(len(pixmaps) > 1)
        right_btn.setVisible(len(pixmaps) > 1)

        center.addWidget(left_btn,  0, Qt.AlignVCenter)
        center.addWidget(self._img_lbl, 1)
        center.addWidget(right_btn, 0, Qt.AlignVCenter)
        root.addLayout(center, 1)

        self._show()

    @staticmethod
    def _make_arrow_btn(filename: str, style: str, size: int) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(size, size)
        btn.setStyleSheet(style)
        path = _RES / filename
        if path.exists():
            icon_px = QPixmap(str(path)).scaled(
                size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            btn.setIcon(icon_px)
            btn.setIconSize(icon_px.size())
        return btn

    def _show(self):
        px = self._pixmaps[self._index]
        if px and not px.isNull():
            screen = self.screen().availableGeometry()
            max_w  = screen.width()  - 160
            max_h  = screen.height() - 160
            scaled = px.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._img_lbl.setPixmap(scaled)
            self.resize(scaled.width() + 160, scaled.height() + 100)
        self._center_on_screen()

    def _center_on_screen(self):
        screen = self.screen().availableGeometry()
        self.move(
            screen.x() + (screen.width()  - self.width())  // 2,
            screen.y() + (screen.height() - self.height()) // 2,
        )

    def _prev(self):
        self._index = (self._index - 1) % len(self._pixmaps)
        self._show()

    def _next(self):
        self._index = (self._index + 1) % len(self._pixmaps)
        self._show()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Left,  Qt.Key_Up):
            self._prev()
        elif event.key() in (Qt.Key_Right, Qt.Key_Down, Qt.Key_Space):
            self._next()
        elif event.key() == Qt.Key_Escape:
            self.close()


# ── Анимированный холст ───────────────────────────────────────────────────────

class _SlideView(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cur: QPixmap | None = None
        self._nxt: QPixmap | None = None
        self._offset = 0.0
        self.setMinimumHeight(280)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(QCursor(Qt.PointingHandCursor))

    def show_current(self, px: QPixmap | None):
        self._cur = px
        self._nxt = None
        self._offset = 0.0
        self.update()

    def prepare_next(self, px: QPixmap | None):
        self._nxt = px

    def _get_offset(self):
        return self._offset

    def _set_offset(self, v: float):
        self._offset = v
        self.update()

    slideOffset = Property(float, _get_offset, _set_offset)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        clip = QPainterPath()
        clip.addRoundedRect(0, 0, w, h, _RADIUS, _RADIUS)
        p.setClipPath(clip)

        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, QColor(20, 8, 8, 230))
        grad.setColorAt(1, QColor(10, 4, 4, 250))
        p.fillPath(clip, grad)

        p.setClipping(False)
        p.setPen(QColor(200, 25, 25, 60))
        p.drawRoundedRect(0, 0, w - 1, h - 1, _RADIUS, _RADIUS)
        p.setClipPath(clip)

        shift = int(self._offset * w)

        def draw(px, x_base):
            if px and not px.isNull():
                s = px.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                p.drawPixmap(x_base + (w - s.width()) // 2, (h - s.height()) // 2, s)

        draw(self._cur, -shift)
        if self._nxt:
            draw(self._nxt, w - shift)
        p.end()


# ── Точки-индикаторы ──────────────────────────────────────────────────────────

class _DotRow(QWidget):
    def __init__(self, count: int, parent=None):
        super().__init__(parent)
        self._count  = count
        self._active = 0
        self.setFixedHeight(18)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_active(self, idx: int):
        if self._active != idx:
            self._active = idx
            self.update()

    def paintEvent(self, event):
        if not self._count:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s, a, g = 7, 9, 9
        total = self._count * a + (self._count - 1) * g
        x0 = (self.width() - total) // 2
        cy = self.height() // 2
        for i in range(self._count):
            size  = a if i == self._active else s
            color = QColor("#ff4040") if i == self._active else QColor(80, 30, 30, 150)
            x = x0 + i * (a + g) + (a - size) // 2
            y = cy - size // 2
            p.setBrush(QBrush(color))
            p.setPen(Qt.NoPen)
            p.drawEllipse(x, y, size, size)
        p.end()


# ── Карусель ─────────────────────────────────────────────────────────────────

class ImageCarousel(QWidget):
    """
    Анимированная карусель.
    sources — список URL-строк или локальных путей к файлам.
    """

    def __init__(self, sources: list[str], tool_name: str = "", parent=None):
        super().__init__(parent)
        self._sources   = sources
        self._tool_name = tool_name
        self._pixmaps: list[QPixmap | None] = []
        self._index     = 0
        self._animating = False
        self._loader: _UrlLoader | None = None
        self._anim:   QPropertyAnimation | None = None

        self.setMinimumSize(480, 280)
        self._build()
        self._init_data()

        self._timer = QTimer(self)
        self._timer.setInterval(_INTERVAL_MS)
        self._timer.timeout.connect(self._auto_advance)
        if len(sources) > 1:
            self._timer.start()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(6)

        self._view = _SlideView(self)
        self._view.clicked.connect(self._open_lightbox)
        lay.addWidget(self._view, stretch=1)

        arrow_style = (
            "QPushButton { background: transparent; border: none; }"
            "QPushButton:hover { background: transparent; }"
            "QPushButton:pressed { background: transparent; }"
        )

        self._prev_btn = self._make_arrow_btn("arrow_left.png",  arrow_style, 34)
        self._next_btn = self._make_arrow_btn("arrow_right.png", arrow_style, 34)
        self._prev_btn.clicked.connect(self._prev)
        self._next_btn.clicked.connect(self._next)

        self._dots = _DotRow(max(len(self._sources), 1), self)

        nav = QHBoxLayout()
        nav.setSpacing(10)
        nav.addStretch()
        nav.addWidget(self._prev_btn)
        nav.addWidget(self._dots)
        nav.addWidget(self._next_btn)
        nav.addStretch()
        lay.addLayout(nav)

    @staticmethod
    def _make_arrow_btn(filename: str, style: str, size: int) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(size, size)
        btn.setStyleSheet(style)
        path = _RES / filename
        if path.exists():
            icon_px = QPixmap(str(path)).scaled(
                size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            btn.setIcon(icon_px)
            btn.setIconSize(icon_px.size())
        return btn

    # ── Данные ───────────────────────────────────────────────────────────────

    def _init_data(self):
        if not self._sources:
            self._pixmaps = [_placeholder(self._tool_name or "Скриншот")]
            self._view.show_current(self._pixmaps[0])
            self._prev_btn.setVisible(False)
            self._next_btn.setVisible(False)
            self._dots.setVisible(False)
            return

        self._pixmaps = [None] * len(self._sources)
        url_indices   = []

        for i, src in enumerate(self._sources):
            if src.startswith("http://") or src.startswith("https://"):
                url_indices.append(i)
            else:
                px = QPixmap(src)
                self._pixmaps[i] = px if not px.isNull() else _placeholder(self._tool_name or "Скриншот")

        self._show(0)

        if url_indices:
            urls = [self._sources[i] for i in url_indices]
            self._loader = _UrlLoader(urls)
            self._loader.loaded.connect(
                lambda order_idx, px: self._on_url_loaded(url_indices[order_idx], px)
            )
            self._loader.start()

    def _on_url_loaded(self, src_idx: int, px: QPixmap):
        self._pixmaps[src_idx] = px
        if src_idx == self._index:
            self._view.show_current(px)

    # ── Отображение ──────────────────────────────────────────────────────────

    def _show(self, idx: int):
        self._index = idx
        px = self._pixmaps[idx] if self._pixmaps else None
        if px is None:
            px = _placeholder(self._tool_name or "Загрузка...")
        self._view.show_current(px)
        self._dots.set_active(idx)

    # ── Лайтбокс ─────────────────────────────────────────────────────────────

    def _open_lightbox(self):
        loaded = [px for px in self._pixmaps if px and not px.isNull()]
        if not loaded:
            return
        dlg = _Lightbox(self._pixmaps, self._index, parent=self.window())
        self._timer.stop()
        dlg.exec()
        self._timer.start()

    # ── Анимация ─────────────────────────────────────────────────────────────

    def _animate_to(self, next_idx: int):
        if self._animating or next_idx == self._index:
            return
        nxt_px = self._pixmaps[next_idx] or _placeholder(self._tool_name or "")
        self._animating = True
        self._view.prepare_next(nxt_px)

        self._anim = QPropertyAnimation(self._view, b"slideOffset")
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(_ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(lambda: self._on_done(next_idx))
        self._anim.start()

    def _on_done(self, idx: int):
        self._index = idx
        px = self._pixmaps[idx] or _placeholder(self._tool_name or "")
        self._view.show_current(px)
        self._dots.set_active(idx)
        self._animating = False
        self._timer.start()

    # ── Навигация ────────────────────────────────────────────────────────────

    def _prev(self):
        if len(self._pixmaps) > 1:
            self._animate_to((self._index - 1) % len(self._pixmaps))

    def _next(self):
        if len(self._pixmaps) > 1:
            self._animate_to((self._index + 1) % len(self._pixmaps))

    def _auto_advance(self):
        if not self._animating:
            self._next()
