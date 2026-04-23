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


def register_user(username, password):
    username = username.strip()

    if username == "" or password == "":
        return False, "Username et mot de passe obligatoires."

    conn = get_connection()
    cursor = conn.cursor()
    username_sql = username.replace("'", "''")
    cursor.execute(f"SELECT pseudo FROM users WHERE pseudo = '{username_sql}'")
    existing_user = cursor.fetchone()
    if existing_user is not None:
        cursor.close()
        conn.close()
        return False, "Ce username existe deja."

    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    hashed_password_str = hashed_password.decode("utf-8")
    _, public_key_pem = generate_and_store_keys(username)
    hashed_password_sql = hashed_password_str.replace("'", "''")
    public_key_sql = public_key_pem.replace("'", "''")

    insert_query = (
        "INSERT INTO users (pseudo, motdepasseHASH, `cléPublic`) "
        f"VALUES ('{username_sql}', '{hashed_password_sql}', '{public_key_sql}')"
    )
    cursor.execute(insert_query)
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
    username_sql = username.replace("'", "''")
    cursor.execute(f"SELECT motdepasseHASH FROM users WHERE pseudo = '{username_sql}'")
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
            QMessageBox.information(self, "Connexion", message)
        else:
            QMessageBox.warning(self, "Connexion", message)


if __name__ == "__main__":
    app = QApplication([])
    window = LoginWindow()
    window.show()
    app.exec()