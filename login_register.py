import re

import bcrypt
import mysql.connector
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import re

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
}
DB_NAME = "pyssst"
PRIVATE_KEY_DIR = Path(__file__).resolve().parent


def generate_and_store_keys(username):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_key_path = PRIVATE_KEY_DIR / f"{username}_private_key.pem"
    with open(private_key_path, "wb") as key_file:
        key_file.write(private_key_pem)

    return str(private_key_path), public_key_pem.decode("utf-8")


def get_connection():
    config = DB_CONFIG.copy()
    config["database"] = DB_NAME
    return mysql.connector.connect(**config)

def validate_password_strength(password):
    if len(password) < 8:
        return False, "Mot de passe trop court (minimum 8 caracteres)."
    if re.search(r"\s", password) is not None:
        return False, "Le mot de passe ne doit pas contenir d'espaces."
    if re.search(r"[a-z]", password) is None:
        return False, "Le mot de passe doit contenir au moins une minuscule."
    if re.search(r"[A-Z]", password) is None:
        return False, "Le mot de passe doit contenir au moins une majuscule."
    if re.search(r"[0-9]", password) is None:
        return False, "Le mot de passe doit contenir au moins un chiffre."
    if re.search(r"[^a-zA-Z0-9]", password) is None:
        return (
            False,
            "Le mot de passe doit contenir au moins un caractere special (ex: !, @, #).",
        )
    return True, ""
def register_user(username, password):
    username = username.strip()

    if username == "" or password == "":
        return False, "Username et mot de passe obligatoires."

    ok, message = validate_password_strength(password)
    if not ok:
        return False, message


    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT pseudo FROM users WHERE pseudo = %s", (username,))
    existing_user = cursor.fetchone()
    if existing_user is not None:
        cursor.close()
        conn.close()
        return False, "Ce username existe deja."

    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    hashed_password_str = hashed_password.decode("utf-8")
    _, public_key_pem = generate_and_store_keys(username)

    cursor.execute(
        "INSERT INTO users (pseudo, motdepasseHASH, `cléPublic`) VALUES (%s, %s, %s)",
        (username, hashed_password_str, public_key_pem),
    )
    conn.commit()
    cursor.close()
    conn.close()
    return True, "Inscription reussie. Cle privee enregistree."


def login_user(username, password):
    username = username.strip()

    if username == "" or password == "":
        return False, "Username et mot de passe obligatoires."

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT motdepasseHASH FROM users WHERE pseudo = %s", (username,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if row is None:
        return False, "Utilisateur introuvable."

    stored_hash = row[0].encode("utf-8")
    if bcrypt.checkpw(password.encode("utf-8"), stored_hash):
        return True, "Connexion reussie."
    return False, "Mot de passe incorrect."


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login/Register")
        self.setGeometry(100, 100, 320, 220)

        self.layout = QVBoxLayout()

        self.username_label = QLabel("Username:")
        self.username_input = QLineEdit()
        self.password_label = QLabel("Password:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)

        self.register_button = QPushButton("Register")
        self.login_button = QPushButton("Login")

        self.layout.addWidget(self.username_label)
        self.layout.addWidget(self.username_input)
        self.layout.addWidget(self.password_label)
        self.layout.addWidget(self.password_input)
        self.layout.addWidget(self.register_button)
        self.layout.addWidget(self.login_button)

        self.setLayout(self.layout)

        self.register_button.clicked.connect(self.register)
        self.login_button.clicked.connect(self.login)

    def register(self):
        username = self.username_input.text()
        password = self.password_input.text()
        ok, message = register_user(username, password)
        if ok:
            QMessageBox.information(self, "Inscription", message)
        else:
            QMessageBox.warning(self, "Inscription", message)

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



if __name__ == "__main__":
    app = QApplication([])
    window = LoginWindow()
    window.show()
    app.exec()