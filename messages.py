import mysql.connector
from db import get_connection
from crypto import encrypt, decrypt, load_private_key


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


def envoyer_message(expediteur, destinataire, texte):
    """Chiffre le texte deux fois et sauvegarde le message en BDD."""
    chiffre_dest = encrypt(texte, get_public_key(destinataire))
    chiffre_exp = encrypt(texte, get_public_key(expediteur))
    save_message(expediteur, destinataire, chiffre_dest, chiffre_exp)


def modifier_message(msg_id, expediteur, destinataire, nouveau_texte):
    """Rechiffre un message modifié et met à jour la BDD."""
    chiffre_dest = encrypt(nouveau_texte, get_public_key(destinataire))
    chiffre_exp = encrypt(nouveau_texte, get_public_key(expediteur))
    return update_message(msg_id, expediteur, chiffre_dest, chiffre_exp)


def _calculer_signature(rows):
    if not rows:
        return (0, 0, "", "")
    last_id = max(r[0] for r in rows)
    modifie_vals = [r[6] for r in rows if r[6] is not None]
    max_modifie = max(modifie_vals) if modifie_vals else None
    lu_vals = tuple(r[7] for r in rows)
    return (len(rows), last_id, str(max_modifie), str(lu_vals))


def charger_conversation(viewer, other_user):
    """Charge et déchiffre tous les messages d'une conversation.
    Retourne (liste_messages, signature).
    Chaque message : (msg_id, expediteur, texte, heure, sent_by_me, modifie, lu).
    """
    private_key = load_private_key(viewer)
    rows = fetch_messages(viewer, other_user)
    signature = _calculer_signature(rows)
    result = []
    for row in rows:
        msg_id, expediteur, destinataire, chiffre_dest, chiffre_exp, envoye_le, modifie_le, lu = row
        sent_by_me = str(expediteur).strip() == str(viewer).strip()
        try:
            texte = decrypt(chiffre_exp if sent_by_me else chiffre_dest, private_key)
        except Exception:
            texte = "[illisible]"
        heure = envoye_le.strftime("%H:%M") if hasattr(envoye_le, "strftime") else str(envoye_le)
        lu_bool = bool(lu) if lu is not None else False
        result.append((msg_id, str(expediteur).strip(), texte, heure, sent_by_me, modifie_le is not None, lu_bool))
    return result, signature
