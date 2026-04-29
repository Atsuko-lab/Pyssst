import mysql.connector
from db import get_connection
from crypto import encrypt, decrypt, load_private_key


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
    cursor.execute(
        "INSERT INTO messages (expediteur, destinataire, contenu_chiffre_dest, contenu_chiffre_exp) VALUES (%s, %s, %s, %s)",
        (str(expediteur).strip(), str(destinataire).strip(), chiffre_dest, chiffre_exp),
    )
    conn.commit()
    cursor.close()
    conn.close()


def mark_messages_as_read(viewer, sender):
    """Marque comme lus tous les messages reçus de 'sender' par 'viewer'."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE messages SET lu = 1 WHERE expediteur = %s AND destinataire = %s AND COALESCE(lu, 0) = 0",
        (sender, viewer),
    )
    conn.commit()
    cursor.close()
    conn.close()


def get_unread_count(viewer, sender):
    """Retourne le nombre de messages non lus envoyés par 'sender' à 'viewer'."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM messages WHERE expediteur = %s AND destinataire = %s AND COALESCE(lu, 0) = 0 AND COALESCE(supprime_pour_tous, 0) = 0",
        (sender, viewer),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row[0] if row else 0


def update_message(msg_id, expediteur, chiffre_dest, chiffre_exp):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE messages SET contenu_chiffre_dest = %s, contenu_chiffre_exp = %s, modifie_le = NOW() "
            "WHERE id = %s AND expediteur = %s AND COALESCE(supprime_pour_tous, 0) = 0",
            (chiffre_dest, chiffre_exp, msg_id, expediteur),
        )
        conn.commit()
        return cursor.rowcount == 1
    except mysql.connector.Error:
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def delete_message_for_me(msg_id, expediteur):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE messages SET cache_par_expediteur = 1 "
            "WHERE id = %s AND expediteur = %s AND COALESCE(supprime_pour_tous, 0) = 0",
            (msg_id, expediteur),
        )
        conn.commit()
        return cursor.rowcount == 1
    except mysql.connector.Error:
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def delete_message_for_everyone(msg_id, expediteur):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE messages SET supprime_pour_tous = 1, supprime_le = NOW(), contenu_chiffre_dest = %s, contenu_chiffre_exp = %s "
            "WHERE id = %s AND expediteur = %s AND COALESCE(supprime_pour_tous, 0) = 0",
            (b"", b"", msg_id, expediteur),
        )
        conn.commit()
        return cursor.rowcount == 1
    except mysql.connector.Error:
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def fetch_messages(viewer, other_user):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, expediteur, destinataire, contenu_chiffre_dest, contenu_chiffre_exp, envoye_le, modifie_le, lu "
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


def _calculer_signature(rows):
    if not rows:
        return (0, 0, "", "")
    last_id = max(r[0] for r in rows)
    modifie_vals = [r[6] for r in rows if r[6] is not None]
    max_modifie = max(modifie_vals) if modifie_vals else None
    lu_vals = tuple(r[7] for r in rows)
    return (len(rows), last_id, str(max_modifie), str(lu_vals))


class Message:
    """Représente un message individuel déjà déchiffré."""

    def __init__(self, msg_id, expediteur, texte, heure, sent_by_me, modifie, lu):
        self.id = msg_id
        self.expediteur = expediteur
        self.texte = texte
        self.heure = heure
        self.sent_by_me = sent_by_me
        self.modifie = modifie
        self.lu = lu

    def __repr__(self):
        return f"Message(id={self.id}, de={self.expediteur!r}, texte={self.texte!r})"


class Conversation:
    """Représente l'échange entre deux utilisateurs."""

    def __init__(self, utilisateur, autre):
        self.utilisateur = utilisateur
        self.autre = autre
        self.messages = []
        self.signature = None

    def charger(self):
        """Charge et déchiffre les messages depuis la BDD."""
        private_key = load_private_key(self.utilisateur.pseudo)
        rows = fetch_messages(self.utilisateur.pseudo, self.autre.pseudo)
        self.signature = _calculer_signature(rows)
        result = []
        for row in rows:
            msg_id, expediteur, destinataire, chiffre_dest, chiffre_exp, envoye_le, modifie_le, lu = row
            sent_by_me = str(expediteur).strip() == str(self.utilisateur.pseudo).strip()
            try:
                texte = decrypt(chiffre_exp if sent_by_me else chiffre_dest, private_key)
            except Exception:
                texte = "[illisible]"
            heure = envoye_le.strftime("%H:%M") if hasattr(envoye_le, "strftime") else str(envoye_le)
            lu_bool = bool(lu) if lu is not None else False
            result.append(Message(msg_id, str(expediteur).strip(), texte, heure, sent_by_me, modifie_le is not None, lu_bool))
        self.messages = result

    def verifier_changements(self):
        """Vérifie si la conversation a changé. Si oui, recharge les messages."""
        rows = fetch_messages(self.utilisateur.pseudo, self.autre.pseudo)
        nouvelle_sig = _calculer_signature(rows)
        if nouvelle_sig == self.signature:
            return False
        private_key = load_private_key(self.utilisateur.pseudo)
        self.signature = nouvelle_sig
        result = []
        for row in rows:
            msg_id, expediteur, destinataire, chiffre_dest, chiffre_exp, envoye_le, modifie_le, lu = row
            sent_by_me = str(expediteur).strip() == str(self.utilisateur.pseudo).strip()
            try:
                texte = decrypt(chiffre_exp if sent_by_me else chiffre_dest, private_key)
            except Exception:
                texte = "[illisible]"
            heure = envoye_le.strftime("%H:%M") if hasattr(envoye_le, "strftime") else str(envoye_le)
            lu_bool = bool(lu) if lu is not None else False
            result.append(Message(msg_id, str(expediteur).strip(), texte, heure, sent_by_me, modifie_le is not None, lu_bool))
        self.messages = result
        return True

    def envoyer(self, texte):
        """Chiffre et envoie un nouveau message."""
        chiffre_dest = encrypt(texte, get_public_key(self.autre.pseudo))
        chiffre_exp = encrypt(texte, get_public_key(self.utilisateur.pseudo))
        save_message(self.utilisateur.pseudo, self.autre.pseudo, chiffre_dest, chiffre_exp)

    def modifier(self, msg_id, nouveau_texte):
        """Rechiffre et met à jour un message existant."""
        chiffre_dest = encrypt(nouveau_texte, get_public_key(self.autre.pseudo))
        chiffre_exp = encrypt(nouveau_texte, get_public_key(self.utilisateur.pseudo))
        return update_message(msg_id, self.utilisateur.pseudo, chiffre_dest, chiffre_exp)

    def supprimer_pour_moi(self, msg_id):
        """Cache le message uniquement pour l'expéditeur connecté."""
        return delete_message_for_me(msg_id, self.utilisateur.pseudo)

    def supprimer_pour_tous(self, msg_id):
        """Supprime le message pour les deux côtés de la conversation."""
        return delete_message_for_everyone(msg_id, self.utilisateur.pseudo)

    def marquer_lus(self):
        """Marque tous les messages reçus de l'autre comme lus."""
        mark_messages_as_read(self.utilisateur.pseudo, self.autre.pseudo)

    def non_lus(self):
        """Retourne le nombre de messages non lus envoyés par l'autre."""
        return get_unread_count(self.utilisateur.pseudo, self.autre.pseudo)

    def __repr__(self):
        return (
            f"Conversation({self.utilisateur.pseudo!r} ↔ {self.autre.pseudo!r}, "
            f"{len(self.messages)} messages)"
        )
