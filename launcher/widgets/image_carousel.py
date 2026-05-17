from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QLinearGradient
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy,
)
import requests as _requests


class _ImgLoader(QThread):
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


def _placeholder_pixmap(text: str, w: int = 560, h: int = 320) -> QPixmap:
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
    font = QFont("Segoe UI", 14, QFont.Bold)
    p.setFont(font)
    p.drawText(px.rect(), Qt.AlignCenter, text)
    p.end()
    return px


class ImageCarousel(QWidget):
    def __init__(self, urls: list[str], tool_name: str = "", parent=None):
        super().__init__(parent)
        self._urls       = urls
        self._tool_name  = tool_name
        self._pixmaps: list[QPixmap | None] = [None] * max(len(urls), 1)
        self._index      = 0
        self._loader     = None
        self.setMinimumSize(480, 280)
        self._build()
        self._init_placeholders()
        if urls:
            self._load_images()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        # Main image
        self._img_label = QLabel()
        self._img_label.setAlignment(Qt.AlignCenter)
        self._img_label.setMinimumHeight(280)
        self._img_label.setStyleSheet(
            "background: rgba(8,4,4,220); border: 1px solid rgba(200,25,25,60); border-radius: 10px;"
        )
        self._img_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay.addWidget(self._img_label, stretch=1)

        # Navigation row
        nav = QHBoxLayout()
        nav.setSpacing(8)

        self._prev_btn = QPushButton("‹")
        self._prev_btn.setFixedSize(32, 32)
        self._prev_btn.clicked.connect(self._prev)

        self._counter = QLabel("1 / 1")
        self._counter.setAlignment(Qt.AlignCenter)
        self._counter.setStyleSheet("color: #666; font-size: 11px;")

        self._next_btn = QPushButton("›")
        self._next_btn.setFixedSize(32, 32)
        self._next_btn.clicked.connect(self._next)

        nav.addStretch()
        nav.addWidget(self._prev_btn)
        nav.addWidget(self._counter)
        nav.addWidget(self._next_btn)
        nav.addStretch()
        lay.addLayout(nav)

        self._update_nav()

    def _init_placeholders(self):
        count = max(len(self._urls), 1)
        self._pixmaps = [None] * count
        label = self._tool_name or "Скриншот"
        if not self._urls:
            self._pixmaps = [_placeholder_pixmap(label)]
        self._show(0)

    def _load_images(self):
        self._loader = _ImgLoader(self._urls)
        self._loader.loaded.connect(self._on_loaded)
        self._loader.start()

    def _on_loaded(self, idx: int, px: QPixmap):
        self._pixmaps[idx] = px
        if idx == self._index:
            self._show(self._index)

    def _show(self, idx: int):
        self._index = idx
        px = self._pixmaps[idx]
        if px and not px.isNull():
            scaled = px.scaled(
                self._img_label.width() or 560,
                self._img_label.height() or 300,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self._img_label.setPixmap(scaled)
        else:
            name = self._tool_name or "Загрузка..."
            self._img_label.setPixmap(
                _placeholder_pixmap(name, self._img_label.width() or 560, self._img_label.height() or 300)
            )
        total = max(len(self._pixmaps), 1)
        self._counter.setText(f"{idx + 1} / {total}")
        self._update_nav()

    def _prev(self):
        self._show((self._index - 1) % len(self._pixmaps))

    def _next(self):
        self._show((self._index + 1) % len(self._pixmaps))

    def _update_nav(self):
        many = len(self._pixmaps) > 1
        self._prev_btn.setVisible(many)
        self._next_btn.setVisible(many)
        self._counter.setVisible(many)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._show(self._index)
