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


def ensure_database_schema():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}`")
        cursor.execute(f"USE `{DB_NAME}`")
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS `users` ("
            "`pseudo` varchar(100) NOT NULL, "
            "`motdepasseHASH` varchar(255) NOT NULL, "
            "`cléPublic` text NOT NULL, "
            "PRIMARY KEY (`pseudo`)"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS `messages` ("
            "`id` int NOT NULL AUTO_INCREMENT, "
            "`expediteur` varchar(100) NOT NULL, "
            "`destinataire` varchar(100) NOT NULL, "
            "`contenu_chiffre_dest` mediumblob NOT NULL, "
            "`contenu_chiffre_exp` mediumblob NOT NULL, "
            "`envoye_le` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "`modifie_le` datetime DEFAULT NULL, "
            "`supprime_pour_tous` tinyint(1) NOT NULL DEFAULT 0, "
            "`supprime_le` datetime DEFAULT NULL, "
            "`cache_par_expediteur` tinyint(1) NOT NULL DEFAULT 0, "
            "`cache_par_destinataire` tinyint(1) NOT NULL DEFAULT 0, "
            "PRIMARY KEY (`id`), "
            "KEY `fk_msg_exp` (`expediteur`), "
            "KEY `fk_msg_dest` (`destinataire`)"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
        )

        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = 'messages'",
            (DB_NAME,),
        )
        existing = {row[0] for row in cursor.fetchall()}
        missing = []
        if "modifie_le" not in existing:
            missing.append("ADD COLUMN modifie_le datetime DEFAULT NULL")
        if "supprime_pour_tous" not in existing:
            missing.append("ADD COLUMN supprime_pour_tous tinyint(1) NOT NULL DEFAULT 0")
        if "supprime_le" not in existing:
            missing.append("ADD COLUMN supprime_le datetime DEFAULT NULL")
        if "cache_par_expediteur" not in existing:
            missing.append("ADD COLUMN cache_par_expediteur tinyint(1) NOT NULL DEFAULT 0")
        if "cache_par_destinataire" not in existing:
            missing.append("ADD COLUMN cache_par_destinataire tinyint(1) NOT NULL DEFAULT 0")
        if missing:
            cursor.execute("ALTER TABLE messages " + ", ".join(missing))

        try:
            cursor.execute(
                "ALTER TABLE `messages` "
                "ADD CONSTRAINT `fk_msg_dest` FOREIGN KEY (`destinataire`) REFERENCES `users` (`pseudo`) ON DELETE CASCADE, "
                "ADD CONSTRAINT `fk_msg_exp` FOREIGN KEY (`expediteur`) REFERENCES `users` (`pseudo`) ON DELETE CASCADE"
            )
        except mysql.connector.Error:
            pass

        conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error:
        return


def get_connection():
    config = DB_CONFIG.copy()
    config["database"] = DB_NAME
    try:
        return mysql.connector.connect(**config)
    except mysql.connector.Error as e:
        if getattr(e, "errno", None) == 1049:
            ensure_database_schema()
            return mysql.connector.connect(**config)
        raise

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
