from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QMessageBox, QInputDialog, QScrollArea, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QFont, QColor

from messages import (
    get_all_users, get_unread_count, mark_messages_as_read,
    delete_message_for_me, delete_message_for_everyone,
    envoyer_message, modifier_message, charger_conversation,
)

STYLE = """
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}
QListWidget {
    background-color: #181825;
    border: none;
    border-radius: 8px;
    padding: 4px;
}
QListWidget::item {
    padding: 10px 8px;
    border-radius: 6px;
}
QListWidget::item:selected {
    background-color: #313244;
    color: #cba6f7;
}
QListWidget::item:hover {
    background-color: #2a2b3c;
}
QScrollArea {
    border: none;
    background-color: #1e1e2e;
}
QLineEdit {
    background-color: #313244;
    border: 1px solid #585b70;
    border-radius: 8px;
    padding: 9px 12px;
    color: #cdd6f4;
    font-size: 13px;
}
QLineEdit:focus {
    border: 1px solid #cba6f7;
}
QPushButton#send_btn {
    background-color: #cba6f7;
    color: #1e1e2e;
    border: none;
    border-radius: 8px;
    padding: 9px 18px;
    font-weight: bold;
    font-size: 13px;
    min-width: 80px;
}
QPushButton#send_btn:hover {
    background-color: #b4befe;
}
QPushButton#action_btn {
    background-color: transparent;
    color: #a6adc8;
    border: 1px solid #45475a;
    border-radius: 5px;
    padding: 2px 8px;
    font-size: 11px;
}
QPushButton#action_btn:hover {
    background-color: #313244;
    color: #cdd6f4;
}
QLabel#header_label {
    font-size: 15px;
    font-weight: bold;
    color: #cba6f7;
    padding: 6px 0;
}
QLabel#section_label {
    font-size: 12px;
    color: #a6adc8;
    padding: 6px 4px 2px 4px;
    font-weight: bold;
    letter-spacing: 1px;
}
"""


class MessageBubble(QFrame):
    """Bulle de message individuelle."""

    def __init__(self, msg_id, expediteur, texte, heure, sent_by_me, modifie, lu, on_edit, on_delete):
        super().__init__()
        self.setObjectName("bubble")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 2, 8, 2)

        bubble = QFrame()
        bubble.setMaximumWidth(480)

        if sent_by_me:
            bubble.setStyleSheet(
                "QFrame { background-color: #4c3f77; border-radius: 10px; padding: 6px 10px; }"
            )
        else:
            bubble.setStyleSheet(
                "QFrame { background-color: #313244; border-radius: 10px; padding: 6px 10px; }"
            )

        blayout = QVBoxLayout(bubble)
        blayout.setSpacing(2)
        blayout.setContentsMargins(8, 6, 8, 6)

        if not sent_by_me:
            name_lbl = QLabel(expediteur)
            name_lbl.setStyleSheet("color: #89b4fa; font-weight: bold; font-size: 11px;")
            blayout.addWidget(name_lbl)

        text_lbl = QLabel(texte)
        text_lbl.setWordWrap(True)
        text_lbl.setStyleSheet("color: #cdd6f4; font-size: 13px;")
        blayout.addWidget(text_lbl)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(4)

        suffix = " · modifié" if modifie else ""
        time_lbl = QLabel(f"{heure}{suffix}")
        time_lbl.setStyleSheet("color: #6c7086; font-size: 10px;")
        meta_row.addWidget(time_lbl)

        # Indicateur vu / non vu (uniquement pour mes messages)
        if sent_by_me:
            seen_lbl = QLabel("✓✓" if lu else "✓")
            seen_lbl.setStyleSheet(
                f"color: {'#89b4fa' if lu else '#6c7086'}; font-size: 10px;"
            )
            meta_row.addWidget(seen_lbl)

        meta_row.addStretch()

        if sent_by_me:
            edit_btn = QPushButton("Modifier")
            edit_btn.setObjectName("action_btn")
            edit_btn.clicked.connect(lambda: on_edit(msg_id, texte))
            del_btn = QPushButton("Supprimer")
            del_btn.setObjectName("action_btn")
            del_btn.clicked.connect(lambda: on_delete(msg_id))
            meta_row.addWidget(edit_btn)
            meta_row.addWidget(del_btn)

        blayout.addLayout(meta_row)

        if sent_by_me:
            outer.addStretch()
            outer.addWidget(bubble)
        else:
            outer.addWidget(bubble)
            outer.addStretch()


class ChatWindow(QWidget):
    def __init__(self, username):
        super().__init__()
        self.username = username
        self.selected_user = None
        self.last_signature = None

        self.setWindowTitle(f"Pyssst — {username}")
        self.resize(860, 600)
        self.setStyleSheet(STYLE)
        self.setMinimumSize(600, 400)

        main = QHBoxLayout(self)
        main.setSpacing(0)
        main.setContentsMargins(0, 0, 0, 0)

        # ── Panneau gauche ─────────────────────────────────────────────────
        left_widget = QWidget()
        left_widget.setFixedWidth(200)
        left_widget.setStyleSheet("background-color: #181825;")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(10, 14, 10, 10)
        left_layout.setSpacing(6)

        app_label = QLabel("💬 Pyssst")
        app_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #cba6f7; padding-bottom: 4px;")
        left_layout.addWidget(app_label)

        users_label = QLabel("UTILISATEURS")
        users_label.setObjectName("section_label")
        left_layout.addWidget(users_label)

        self.user_list = QListWidget()
        self.user_list.itemClicked.connect(self.on_user_click)
        left_layout.addWidget(self.user_list)

        self.user_label_bottom = QLabel(f"Connecté : {username}")
        self.user_label_bottom.setStyleSheet("color: #6c7086; font-size: 11px; padding-top: 4px;")
        self.user_label_bottom.setWordWrap(True)
        left_layout.addWidget(self.user_label_bottom)

        # ── Panneau droite ─────────────────────────────────────────────────
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)

        self.chat_label = QLabel("← Sélectionne un utilisateur pour commencer")
        self.chat_label.setObjectName("header_label")
        right_layout.addWidget(self.chat_label)

        # Zone de défilement des messages
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: #1e1e2e; border: none;")

        self.messages_container = QWidget()
        self.messages_container.setStyleSheet("background-color: #1e1e2e;")
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setAlignment(Qt.AlignTop)
        self.messages_layout.setSpacing(4)
        self.messages_layout.setContentsMargins(4, 4, 4, 4)

        self.scroll_area.setWidget(self.messages_container)
        right_layout.addWidget(self.scroll_area, 1)

        # Barre de saisie
        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Écris un message… (Entrée pour envoyer)")
        self.input.returnPressed.connect(self.send_message)
        send_btn = QPushButton("Envoyer")
        send_btn.setObjectName("send_btn")
        send_btn.setCursor(Qt.PointingHandCursor)
        send_btn.clicked.connect(self.send_message)
        input_row.addWidget(self.input)
        input_row.addWidget(send_btn)
        right_layout.addLayout(input_row)

        main.addWidget(left_widget)
        main.addWidget(right_widget, 1)

        self.refresh_users()

        self.timer = QTimer()
        self.timer.timeout.connect(self.poll)
        self.timer.start(2000)

    # ── Gestion des utilisateurs ──────────────────────────────────────────

    def refresh_users(self):
        self.user_list.clear()
        for user in get_all_users(self.username):
            count = get_unread_count(self.username, user)
            display = f"{user}  🔴 {count}" if count > 0 else user
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, user)
            self.user_list.addItem(item)

    def on_user_click(self, item):
        self.selected_user = item.data(Qt.UserRole)
        self.chat_label.setText(f"Conversation avec {self.selected_user}")
        self.last_signature = None
        self.clear_messages()
        mark_messages_as_read(self.username, self.selected_user)
        self.load_messages()
        self.refresh_users()
        self.input.setFocus()

    # ── Affichage des messages ────────────────────────────────────────────

    def clear_messages(self):
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def load_messages(self):
        messages, sig = charger_conversation(self.username, self.selected_user)
        self.last_signature = sig
        for msg in messages:
            self._add_bubble(msg)
        self._scroll_to_bottom()

    def _add_bubble(self, msg):
        msg_id, expediteur, texte, heure, sent_by_me, modifie, lu = msg
        bubble = MessageBubble(
            msg_id=msg_id,
            expediteur=expediteur,
            texte=texte,
            heure=heure,
            sent_by_me=sent_by_me,
            modifie=modifie,
            lu=lu,
            on_edit=self.edit_message,
            on_delete=self.delete_message,
        )
        self.messages_layout.addWidget(bubble)

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))

    # ── Actions messages ──────────────────────────────────────────────────────

    def send_message(self):
        if not self.selected_user:
            QMessageBox.warning(self, "Erreur", "Sélectionne un utilisateur.")
            return
        texte = self.input.text().strip()
        if not texte:
            return
        envoyer_message(self.username, self.selected_user, texte)
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
        if not modifier_message(msg_id, self.username, self.selected_user, nouveau_texte):
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

    # ── Polling ───────────────────────────────────────────────────────────

    def poll(self):
        self.refresh_users()
        if not self.selected_user:
            return
        messages, sig = charger_conversation(self.username, self.selected_user)
        if sig == self.last_signature:
            return
        mark_messages_as_read(self.username, self.selected_user)
        self.clear_messages()
        self.last_signature = sig
        for msg in messages:
            self._add_bubble(msg)
        self._scroll_to_bottom()
