from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QMessageBox, QFrame,
)
from PySide6.QtCore import Qt

from auth import register_user, login_user

STYLE = """
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}
QFrame#card {
    background-color: #313244;
    border-radius: 12px;
}
QLabel#title {
    font-size: 22px;
    font-weight: bold;
    color: #cba6f7;
}
QLabel#subtitle {
    color: #a6adc8;
    font-size: 11px;
}
QLineEdit {
    background-color: #45475a;
    border: 1px solid #585b70;
    border-radius: 6px;
    padding: 8px 10px;
    color: #cdd6f4;
}
QLineEdit:focus {
    border: 1px solid #cba6f7;
}
QPushButton#primary {
    background-color: #cba6f7;
    color: #1e1e2e;
    border: none;
    border-radius: 6px;
    padding: 9px 0;
    font-weight: bold;
    font-size: 13px;
}
QPushButton#primary:hover {
    background-color: #b4befe;
}
QPushButton#secondary {
    background-color: transparent;
    color: #89b4fa;
    border: 1px solid #89b4fa;
    border-radius: 6px;
    padding: 9px 0;
    font-size: 13px;
}
QPushButton#secondary:hover {
    background-color: #1e1e2e;
}
"""


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pyssst — Connexion")
        self.setFixedSize(400, 440)
        self.setStyleSheet(STYLE)

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)
        outer.setContentsMargins(30, 30, 30, 30)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)
        card_layout.setContentsMargins(28, 28, 28, 28)

        title = QLabel("🔐 Pyssst")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Messagerie chiffrée de bout en bout")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Nom d'utilisateur")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Mot de passe")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self.login)

        self.login_button = QPushButton("Se connecter")
        self.login_button.setObjectName("primary")
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.clicked.connect(self.login)

        self.register_button = QPushButton("Créer un compte")
        self.register_button.setObjectName("secondary")
        self.register_button.setCursor(Qt.PointingHandCursor)
        self.register_button.clicked.connect(self.register)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(8)
        card_layout.addWidget(QLabel("Pseudo :"))
        card_layout.addWidget(self.username_input)
        card_layout.addWidget(QLabel("Mot de passe :"))
        card_layout.addWidget(self.password_input)
        card_layout.addSpacing(4)
        card_layout.addWidget(self.login_button)
        card_layout.addWidget(self.register_button)

        outer.addWidget(card)

    def login(self):
        username = self.username_input.text()
        password = self.password_input.text()
        ok, message = login_user(username, password)
        if ok:
            from chat import ChatWindow
            self.chat = ChatWindow(username.strip())
            self.chat.show()
            self.close()
        else:
            QMessageBox.warning(self, "Connexion", message)

    def register(self):
        username = self.username_input.text()
        password = self.password_input.text()
        ok, message = register_user(username, password)
        if ok:
            QMessageBox.information(self, "Inscription", message)
        else:
            QMessageBox.warning(self, "Inscription", message)
