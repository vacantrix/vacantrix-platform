from datetime import datetime, timezone
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtGui import QPixmap, QCursor

from launcher.paths import RESOURCES

TOOL_ICONS: dict[str, str] = {
    "vacantrix": str(RESOURCES / "hh_icon.png"),
    "avito":     str(RESOURCES / "avito_icon.png"),
}


def _days_left(expires_at: str) -> int:
    dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    return max(0, (dt - datetime.now(tz=timezone.utc)).days)


class ToolCard(QFrame):
    clicked        = Signal(dict, object)
    buy_clicked    = Signal(dict)
    launch_clicked = Signal(dict)

    def __init__(self, tool: dict, subscription: dict | None, parent=None):
        super().__init__(parent)
        self._tool = tool
        self._sub  = subscription
        self.setProperty("class", "card")
        self.setFixedSize(240, 280)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 14)
        lay.setSpacing(0)

        # ── Banner image ──
        banner = QLabel()
        banner.setFixedHeight(110)
        banner.setAlignment(Qt.AlignCenter)
        banner.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 rgba(40,5,5,255), stop:1 rgba(15,2,2,255));"
            "border-radius: 12px 12px 0 0;"
        )
        slug = self._tool.get("slug", "")
        icon_path = TOOL_ICONS.get(slug)
        if icon_path and Path(icon_path).exists():
            px = QPixmap(icon_path).scaled(90, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            banner.setPixmap(px)
        else:
            banner.setText(self._tool.get("icon_url") or "🔧")
            banner.setStyleSheet(banner.styleSheet() + " font-size: 40px;")
        lay.addWidget(banner)

        # ── Info area ──
        info = QVBoxLayout()
        info.setContentsMargins(14, 10, 14, 0)
        info.setSpacing(4)

        name = QLabel(self._tool["name"])
        name.setStyleSheet("font-size: 14px; font-weight: bold; color: #eeeef5;")
        info.addWidget(name)

        tagline = QLabel(self._tool.get("tagline") or "")
        tagline.setStyleSheet("color: #666; font-size: 11px;")
        tagline.setWordWrap(True)
        info.addWidget(tagline)

        info.addStretch()

        status = self._tool.get("status", "active")

        if status == "coming_soon":
            st = QLabel("🚧 В разработке")
            st.setStyleSheet("color: #666; font-size: 11px;")
            info.addWidget(st)
            btn = QPushButton("Скоро")
            btn.setEnabled(False)
            btn.setFixedHeight(34)
            info.addWidget(btn)

        elif self._sub and self._sub.get("status") == "active":
            days = _days_left(self._sub["expires_at"])
            st = QLabel(f"✅  Активна: {days} дн.")
            st.setStyleSheet("color: #4caf50; font-size: 11px; font-weight: bold;")
            info.addWidget(st)
            btn = QPushButton("▶  Запустить")
            btn.setFixedHeight(36)
            btn.setStyleSheet("""
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0.00 rgba(255,255,255,55),
                    stop:0.06 rgba(60,200,60,230),
                    stop:0.50 rgba(30,140,30,220),
                    stop:0.92 rgba(10,70,10,240),
                    stop:1.00 rgba(0,30,0,255));
                border-top: 1px solid rgba(120,255,120,150);
                border-bottom: 2px solid rgba(0,20,0,255);
                border-left: 1px solid rgba(60,180,60,100);
                border-right: 1px solid rgba(10,60,10,200);
                border-radius: 8px; color: #ffffff; font-weight: bold;
            """)
            btn.clicked.connect(lambda: self.launch_clicked.emit(self._tool))
            info.addWidget(btn)

        else:
            st = QLabel("🔒  Нет подписки")
            st.setStyleSheet("color: #c41c1c; font-size: 11px; font-weight: bold;")
            info.addWidget(st)
            btn = QPushButton("Купить подписку")
            btn.setFixedHeight(36)
            btn.clicked.connect(lambda: self.buy_clicked.emit(self._tool))
            info.addWidget(btn)

        lay.addLayout(info)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._tool, self._sub)
        super().mousePressEvent(event)
