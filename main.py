import sys
from PySide6.QtWidgets import QApplication
from login_resgister import LoginWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Pyssst")
    window = LoginWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
