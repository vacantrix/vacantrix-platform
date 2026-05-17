from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QStackedWidget, QMessageBox,
)

from launcher.core.auth_manager import AuthManager


class _AuthWorker(QThread):
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, fn, *args):
        super().__init__()
        self._fn = fn
        self._args = args

    def run(self):
        try:
            self.done.emit(self._fn(*self._args))
        except Exception as e:
            self.error.emit(str(e))


class AuthScreen(QWidget):
    logged_in = Signal()

    def __init__(self, auth: AuthManager, parent=None):
        super().__init__(parent)
        self._auth = auth
        self._worker = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        title = QLabel("Vacantrix Platform")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 8px;")
        root.addWidget(title)

        self._tabs = QStackedWidget()
        self._tabs.addWidget(self._build_login())
        self._tabs.addWidget(self._build_register())
        root.addWidget(self._tabs)

        toggle_row = QHBoxLayout()
        self._toggle_label = QLabel("Нет аккаунта?")
        self._toggle_btn = QPushButton("Зарегистрироваться")
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setStyleSheet("color: #4f8ef7; text-decoration: underline;")
        self._toggle_btn.clicked.connect(self._toggle)
        toggle_row.addStretch()
        toggle_row.addWidget(self._toggle_label)
        toggle_row.addWidget(self._toggle_btn)
        toggle_row.addStretch()
        root.addLayout(toggle_row)

        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setStyleSheet("color: #e05050;")
        root.addWidget(self._status)

    def _build_login(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(60, 20, 60, 20)

        self._login_email = QLineEdit()
        self._login_email.setPlaceholderText("Email")
        self._login_pass = QLineEdit()
        self._login_pass.setPlaceholderText("Пароль")
        self._login_pass.setEchoMode(QLineEdit.Password)
        self._login_pass.returnPressed.connect(self._do_login)

        self._login_btn = QPushButton("Войти")
        self._login_btn.clicked.connect(self._do_login)
        self._login_btn.setFixedHeight(40)

        for w_ in (self._login_email, self._login_pass, self._login_btn):
            lay.addWidget(w_)
        return w

    def _build_register(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(60, 20, 60, 20)

        self._reg_email = QLineEdit()
        self._reg_email.setPlaceholderText("Email")
        self._reg_pass = QLineEdit()
        self._reg_pass.setPlaceholderText("Пароль (минимум 6 символов)")
        self._reg_pass.setEchoMode(QLineEdit.Password)
        self._reg_pass2 = QLineEdit()
        self._reg_pass2.setPlaceholderText("Повторите пароль")
        self._reg_pass2.setEchoMode(QLineEdit.Password)
        self._reg_pass2.returnPressed.connect(self._do_register)

        self._reg_btn = QPushButton("Создать аккаунт")
        self._reg_btn.clicked.connect(self._do_register)
        self._reg_btn.setFixedHeight(40)

        for w_ in (self._reg_email, self._reg_pass, self._reg_pass2, self._reg_btn):
            lay.addWidget(w_)
        return w

    def _toggle(self):
        if self._tabs.currentIndex() == 0:
            self._tabs.setCurrentIndex(1)
            self._toggle_label.setText("Уже есть аккаунт?")
            self._toggle_btn.setText("Войти")
        else:
            self._tabs.setCurrentIndex(0)
            self._toggle_label.setText("Нет аккаунта?")
            self._toggle_btn.setText("Зарегистрироваться")
        self._status.setText("")

    def _set_busy(self, busy: bool):
        self._login_btn.setEnabled(not busy)
        self._reg_btn.setEnabled(not busy)
        self._status.setText("Подождите..." if busy else "")

    def _do_login(self):
        email = self._login_email.text().strip()
        pwd   = self._login_pass.text()
        if not email or not pwd:
            self._status.setText("Заполните все поля")
            return
        self._set_busy(True)
        self._worker = _AuthWorker(self._auth.sign_in, email, pwd)
        self._worker.done.connect(lambda _: self.logged_in.emit())
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _do_register(self):
        email = self._reg_email.text().strip()
        pwd   = self._reg_pass.text()
        pwd2  = self._reg_pass2.text()
        if not email or not pwd:
            self._status.setText("Заполните все поля")
            return
        if pwd != pwd2:
            self._status.setText("Пароли не совпадают")
            return
        if len(pwd) < 6:
            self._status.setText("Пароль минимум 6 символов")
            return
        self._set_busy(True)
        self._worker = _AuthWorker(self._auth.sign_up, email, pwd)
        self._worker.done.connect(self._on_registered)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_registered(self, data: dict):
        self._set_busy(False)
        if data.get("access_token"):
            self.logged_in.emit()
        else:
            QMessageBox.information(
                self, "Подтверждение",
                "Письмо отправлено на почту.\nПодтвердите email и войдите.",
            )
            self._toggle()

    def _on_error(self, msg: str):
        self._set_busy(False)
        self._status.setText(msg)
