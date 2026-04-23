from pathlib import Path

import mysql.connector
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox,
    QInputDialog,
    QPushButton, QVBoxLayout, QWidget,
)

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "pyssst",
}

PRIVATE_KEY_DIR = Path(__file__).resolve().parent


def ensure_database_schema():
    try:
        base_config = DB_CONFIG.copy()
        base_config.pop("database", None)
        conn = mysql.connector.connect(**base_config)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}`")
        cursor.execute(f"USE `{DB_CONFIG['database']}`")
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
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as e:
        if getattr(e, "errno", None) == 1049:
            ensure_database_schema()
            return mysql.connector.connect(**DB_CONFIG)
        raise

def ensure_messages_schema():
    required_columns = {
        "modifie_le": "ALTER TABLE messages ADD COLUMN modifie_le datetime DEFAULT NULL",
        "supprime_pour_tous": "ALTER TABLE messages ADD COLUMN supprime_pour_tous tinyint(1) NOT NULL DEFAULT 0",
        "supprime_le": "ALTER TABLE messages ADD COLUMN supprime_le datetime DEFAULT NULL",
        "cache_par_expediteur": "ALTER TABLE messages ADD COLUMN cache_par_expediteur tinyint(1) NOT NULL DEFAULT 0",
        "cache_par_destinataire": "ALTER TABLE messages ADD COLUMN cache_par_destinataire tinyint(1) NOT NULL DEFAULT 0",
    }

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = 'messages'",
            (DB_CONFIG["database"],),
        )
        existing = {row[0] for row in cursor.fetchall()}
        for name, ddl in required_columns.items():
            if name not in existing:
                cursor.execute(ddl)
        conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error:
        return


def get_all_users(exclude):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT pseudo FROM users WHERE pseudo != %s", (exclude,))
    users = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return users


def get_public_key(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT `cléPublic` FROM users WHERE pseudo = %s", (username,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row[0]


def save_message(expediteur, destinataire, chiffre_dest, chiffre_exp):
    conn = get_connection()
    cursor = conn.cursor()
    expediteur = str(expediteur).strip()
    destinataire = str(destinataire).strip()
    cursor.execute(
        "INSERT INTO messages (expediteur, destinataire, contenu_chiffre_dest, contenu_chiffre_exp) VALUES (%s, %s, %s, %s)",
        (expediteur, destinataire, chiffre_dest, chiffre_exp),
    )
    conn.commit()
    cursor.close()
    conn.close()


def update_message(msg_id, expediteur, chiffre_dest, chiffre_exp):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE messages "
        "SET contenu_chiffre_dest = %s, contenu_chiffre_exp = %s, modifie_le = NOW() "
        "WHERE id = %s AND expediteur = %s AND COALESCE(supprime_pour_tous, 0) = 0",
        (chiffre_dest, chiffre_exp, msg_id, expediteur),
    )
    conn.commit()
    ok = cursor.rowcount == 1
    cursor.close()
    conn.close()
    return ok


def delete_message_for_me(msg_id, expediteur):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE messages "
        "SET cache_par_expediteur = 1 "
        "WHERE id = %s AND expediteur = %s AND COALESCE(supprime_pour_tous, 0) = 0",
        (msg_id, expediteur),
    )
    conn.commit()
    ok = cursor.rowcount == 1
    cursor.close()
    conn.close()
    return ok


def delete_message_for_everyone(msg_id, expediteur):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE messages "
        "SET supprime_pour_tous = 1, supprime_le = NOW(), contenu_chiffre_dest = %s, contenu_chiffre_exp = %s "
        "WHERE id = %s AND expediteur = %s AND COALESCE(supprime_pour_tous, 0) = 0",
        (b"", b"", msg_id, expediteur),
    )
    conn.commit()
    ok = cursor.rowcount == 1
    cursor.close()
    conn.close()
    return ok


def fetch_messages(viewer, other_user):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, expediteur, destinataire, contenu_chiffre_dest, contenu_chiffre_exp, envoye_le, modifie_le "
        "FROM messages "
        "WHERE ((expediteur = %s AND destinataire = %s) OR (expediteur = %s AND destinataire = %s)) "
        "AND COALESCE(supprime_pour_tous, 0) = 0 "
        "AND NOT ((expediteur = %s AND COALESCE(cache_par_expediteur, 0) = 1) OR (destinataire = %s AND COALESCE(cache_par_destinataire, 0) = 1)) "
        "ORDER BY envoye_le ASC",
        (viewer, other_user, other_user, viewer, viewer, viewer),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


# le saint chiffrement

def load_private_key(username):
    key_path = PRIVATE_KEY_DIR / f"{username}_private_key.pem"
    with open(key_path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def encrypt(message, public_key_pem):
    public_key = serialization.load_pem_public_key(public_key_pem.encode())
    return public_key.encrypt(
        message.encode(),
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )


def decrypt(ciphertext, private_key):
    return private_key.decrypt(
        bytes(ciphertext),
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    ).decode()


#le chat pour chatter

class ChatWindow(QWidget):
    def __init__(self, username):
        super().__init__()
        self.username = username
        self.selected_user = None
        ensure_messages_schema()
        self.private_key = load_private_key(username)
        self.last_id = 0
        self.last_signature = None

        self.setWindowTitle(f"Chat — {username}")
        self.resize(700, 500)

        main = QHBoxLayout(self)

        # Colonne gauche 
        left = QVBoxLayout()
        left.addWidget(QLabel("Utilisateurs :"))
        self.user_list = QListWidget()
        self.user_list.itemClicked.connect(self.on_user_click)
        left.addWidget(self.user_list)
        left_widget = QWidget()
        left_widget.setFixedWidth(160)
        left_widget.setLayout(left)

        # Colonne droite
        right = QVBoxLayout()
        self.chat_label = QLabel("Sélectionne un utilisateur")
        right.addWidget(self.chat_label)

        self.messages_area = QVBoxLayout()
        self.messages_area.setAlignment(Qt.AlignTop)
        messages_widget = QWidget()
        messages_widget.setLayout(self.messages_area)
        right.addWidget(messages_widget)

        input_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Message...")
        self.input.returnPressed.connect(self.send_message)
        send_btn = QPushButton("Envoyer")
        send_btn.clicked.connect(self.send_message)
        input_row.addWidget(self.input)
        input_row.addWidget(send_btn)
        right.addLayout(input_row)

        main.addWidget(left_widget)
        main.addLayout(right)

        self.refresh_users()

        self.timer = QTimer()
        self.timer.timeout.connect(self.poll)
        self.timer.start(2000)

    def refresh_users(self):
        self.user_list.clear()
        for user in get_all_users(self.username):
            item = QListWidgetItem(user)
            item.setData(Qt.UserRole, user)
            self.user_list.addItem(item)

    def on_user_click(self, item):
        self.selected_user = item.data(Qt.UserRole)
        self.chat_label.setText(f"Conversation avec {self.selected_user}")
        self.last_id = 0
        self.last_signature = None
        self.clear_messages()
        self.load_messages()

    def clear_messages(self):
        while self.messages_area.count():
            w = self.messages_area.takeAt(0).widget()
            if w:
                w.deleteLater()

    def load_messages(self):
        rows = fetch_messages(self.username, self.selected_user)
        self.last_signature = self.compute_signature(rows)
        for row in rows:
            msg_id, expediteur, destinataire, chiffre_dest, chiffre_exp, envoye_le, modifie_le = row
            self.show_message(msg_id, expediteur, destinataire, chiffre_dest, chiffre_exp, envoye_le, modifie_le)

    def compute_signature(self, rows):
        if not rows:
            return (0, 0, "")
        last_id = max(r[0] for r in rows)
        modifie_le_vals = [r[6] for r in rows if r[6] is not None]
        max_modifie = max(modifie_le_vals) if modifie_le_vals else None
        return (len(rows), last_id, str(max_modifie) if max_modifie is not None else "")

    def show_message(self, msg_id, expediteur, destinataire, chiffre_dest, chiffre_exp, envoye_le, modifie_le):
        sent_by_me = (str(expediteur).strip() == str(self.username).strip())
        try:
            texte = decrypt(chiffre_exp if sent_by_me else chiffre_dest, self.private_key)
        except Exception:
            texte = "[illisible]"

        heure = envoye_le.strftime("%H:%M") if hasattr(envoye_le, "strftime") else str(envoye_le)
        prefix = "Moi" if sent_by_me else expediteur
        suffix = " (modifié)" if modifie_le is not None else ""
        label = QLabel(f"[{heure}] {prefix} : {texte}{suffix}")
        label.setWordWrap(True)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(label, 1)

        if sent_by_me:
            edit_btn = QPushButton("Modifier")
            edit_btn.clicked.connect(lambda _=False, mid=msg_id, txt=texte: self.edit_message(mid, txt))
            del_btn = QPushButton("Supprimer")
            del_btn.clicked.connect(lambda _=False, mid=msg_id: self.delete_message(mid))
            row_layout.addWidget(edit_btn)
            row_layout.addWidget(del_btn)

        self.messages_area.addWidget(row)

        if msg_id > self.last_id:
            self.last_id = msg_id

    def send_message(self):
        if not self.selected_user:
            QMessageBox.warning(self, "Erreur", "Sélectionne un utilisateur.")
            return
        texte = self.input.text().strip()
        if not texte:
            return

        chiffre_dest = encrypt(texte, get_public_key(self.selected_user))
        chiffre_exp = encrypt(texte, get_public_key(self.username))

        save_message(self.username, self.selected_user, chiffre_dest, chiffre_exp)
        self.input.clear()
        self.clear_messages()
        self.load_messages()

    def edit_message(self, msg_id, ancien_texte):
        if not self.selected_user:
            return
        nouveau_texte, ok = QInputDialog.getText(self, "Modifier", "Nouveau message :", text=ancien_texte)
        if not ok:
            return
        nouveau_texte = nouveau_texte.strip()
        if not nouveau_texte:
            QMessageBox.warning(self, "Erreur", "Le message ne peut pas être vide.")
            return

        chiffre_dest = encrypt(nouveau_texte, get_public_key(self.selected_user))
        chiffre_exp = encrypt(nouveau_texte, get_public_key(self.username))
        if not update_message(msg_id, self.username, chiffre_dest, chiffre_exp):
            QMessageBox.warning(self, "Erreur", "Impossible de modifier ce message.")
            return
        self.clear_messages()
        self.load_messages()

    def delete_message(self, msg_id):
        box = QMessageBox(self)
        box.setWindowTitle("Supprimer")
        box.setText("Supprimer ce message ?")
        btn_me = box.addButton("Pour moi", QMessageBox.AcceptRole)
        btn_all = box.addButton("Pour tout le monde", QMessageBox.DestructiveRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        clicked = box.clickedButton()

        if clicked == btn_me:
            ok = delete_message_for_me(msg_id, self.username)
        elif clicked == btn_all:
            ok = delete_message_for_everyone(msg_id, self.username)
        else:
            return

        if not ok:
            QMessageBox.warning(self, "Erreur", "Impossible de supprimer ce message.")
            return
        self.clear_messages()
        self.load_messages()

    def poll(self):
        if not self.selected_user:
            return
        rows = fetch_messages(self.username, self.selected_user)
        signature = self.compute_signature(rows)
        if signature == self.last_signature:
            return
        self.clear_messages()
        self.last_signature = signature
        for row in rows:
            msg_id, expediteur, destinataire, chiffre_dest, chiffre_exp, envoye_le, modifie_le = row
            self.show_message(msg_id, expediteur, destinataire, chiffre_dest, chiffre_exp, envoye_le, modifie_le)
