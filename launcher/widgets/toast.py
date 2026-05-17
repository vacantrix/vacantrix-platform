from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QLabel, QWidget


class Toast(QLabel):
    def __init__(self, message: str, parent: QWidget, duration: int = 3000):
        super().__init__(message, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            background: rgba(30, 30, 50, 220);
            color: #fff;
            border: 1px solid #4f8ef7;
            border-radius: 8px;
            padding: 10px 20px;
            font-size: 13px;
        """)
        self.adjustSize()
        self._reposition()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.show()
        self.raise_()

        QTimer.singleShot(duration, self._fade_out)

    def _reposition(self):
        parent = self.parent()
        if parent:
            pw, ph = parent.width(), parent.height()
            w, h   = self.width(), self.height()
            self.move((pw - w) // 2, ph - h - 24)

    def _fade_out(self):
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(400)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.InQuad)
        self._anim.finished.connect(self.deleteLater)
        self._anim.start()


def show_toast(message: str, parent: QWidget, duration: int = 3000) -> Toast:
    return Toast(message, parent, duration)
