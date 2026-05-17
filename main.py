import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt
from launcher.app import MainWindow
from launcher import theme

RESOURCES = Path(__file__).parent / "resources"


def main():
    # Proper standalone app — no console flicker on Windows
    app = QApplication(sys.argv)
    app.setApplicationName("Vacantrix Platform")
    app.setApplicationDisplayName("Vacantrix Platform")
    app.setOrganizationName("Vacantrix")

    # App icon (taskbar + title bar)
    icon_path = RESOURCES / "vacantrix_icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    theme.apply(app)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
