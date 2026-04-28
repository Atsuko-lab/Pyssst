from db import get_connection


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
