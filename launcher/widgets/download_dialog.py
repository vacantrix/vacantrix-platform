from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton,
)

from launcher.core.downloader import DownloadWorker


class DownloadDialog(QDialog):
    def __init__(self, tool: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Скачивание — {tool['name']}")
        self.setFixedSize(400, 160)
        self.setModal(True)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(20, 16, 20, 16)

        self._label = QLabel(f"Скачиваем {tool['name']}...")
        self._label.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._label)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        lay.addWidget(self._bar)

        self._size_lbl = QLabel("")
        self._size_lbl.setAlignment(Qt.AlignCenter)
        self._size_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        lay.addWidget(self._size_lbl)

        self._cancel_btn = QPushButton("✕  Отмена")
        self._cancel_btn.setFixedHeight(32)
        self._cancel_btn.setProperty("class", "danger")
        self._cancel_btn.clicked.connect(self._on_cancel)
        lay.addWidget(self._cancel_btn)

        self._worker = DownloadWorker(
            slug=tool["slug"],
            download_url=tool["download_url"],
            version=tool.get("version", ""),
            exe_name=tool["name"],
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    # ── Worker callbacks ──────────────────────────────────────────────────────

    def _on_progress(self, done: int, total: int):
        if total > 0:
            self._bar.setValue(int(done / total * 100))
            self._size_lbl.setText(
                f"{done // 1_048_576} МБ / {total // 1_048_576} МБ"
            )
        else:
            self._bar.setRange(0, 0)
            self._size_lbl.setText(f"{done // 1_048_576} МБ...")

    def _on_finished(self):
        self._cancel_btn.setEnabled(False)
        self.accept()

    def _on_error(self, msg: str):
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._label.setText(f"Ошибка: {msg}")
        self._label.setStyleSheet("color: #e05050;")
        self._cancel_btn.setText("Закрыть")
        self._cancel_btn.setProperty("class", "")
        self._cancel_btn.style().unpolish(self._cancel_btn)
        self._cancel_btn.style().polish(self._cancel_btn)
        self._cancel_btn.clicked.disconnect()
        self._cancel_btn.clicked.connect(self.reject)

    # ── Cancel / close ────────────────────────────────────────────────────────

    def _on_cancel(self):
        self._worker.cancel()
        self._worker.wait(3000)
        self.reject()

    def closeEvent(self, event):
        if self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        event.accept()
