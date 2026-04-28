import re
import os
import hmac
import hashlib
import bcrypt
import mysql.connector

from db import get_connection, format_db_error
from crypto import generate_and_store_keys


def _encrypt_password(password: str) -> str:
    """Étape 1 — Cryptage : HMAC-SHA256 du mot de passe avec une clé secrète applicative."""
    secret_key = os.environ.get("PYSSST_SECRET_KEY", "Py$$st_S3cretK3y_2026").encode("utf-8")
    return hmac.new(secret_key, password.encode("utf-8"), hashlib.sha256).hexdigest()


def _salt_and_hash(encrypted: str) -> str:
    """Étape 2 — Salage : bcrypt génère un sel aléatoire unique par utilisateur et hache le résultat."""
    return bcrypt.hashpw(encrypted.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def validate_password_strength(password):
    if len(password) < 8:
        return False, "Mot de passe trop court (minimum 8 caractères)."
    if re.search(r"\s", password) is not None:
        return False, "Le mot de passe ne doit pas contenir d'espaces."
    if re.search(r"[a-z]", password) is None:
        return False, "Le mot de passe doit contenir au moins une minuscule."
    if re.search(r"[A-Z]", password) is None:
        return False, "Le mot de passe doit contenir au moins une majuscule."
    if re.search(r"[0-9]", password) is None:
        return False, "Le mot de passe doit contenir au moins un chiffre."
    if re.search(r"[^a-zA-Z0-9]", password) is None:
        return False, "Le mot de passe doit contenir au moins un caractère spécial (ex: !, @, #)."
    for name in ("Isham", "Nathan", "Fady"):
        if re.search(name, password, re.IGNORECASE) is not None:
            return False, f"Le mot de passe ne doit pas contenir '{name}'."
    return True, ""


def register_user(username, password):
    username = username.strip()
    if username == "" or password == "":
        return False, "Username et mot de passe obligatoires."

    ok, message = validate_password_strength(password)
    if not ok:
        return False, message

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT pseudo FROM users WHERE pseudo = %s", (username,))
        if cursor.fetchone() is not None:
            return False, "Ce username existe déjà."

        encrypted = _encrypt_password(password)
        hashed_password_str = _salt_and_hash(encrypted)
        _, public_key_pem = generate_and_store_keys(username)

        cursor.execute(
            "INSERT INTO users (pseudo, motdepasseHASH_SAL, `cléPublic`) VALUES (%s, %s, %s)",
            (username, hashed_password_str, public_key_pem),
        )
        conn.commit()
        return True, "Inscription réussie. Clé privée enregistrée dans le dossier 'clé'."
    except mysql.connector.Error as e:
        return False, format_db_error(e)
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def login_user(username, password):
    username = username.strip()
    if username == "" or password == "":
        return False, "Username et mot de passe obligatoires."

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT motdepasseHASH_SAL FROM users WHERE pseudo = %s", (username,))
        row = cursor.fetchone()
        if row is None:
            return False, "Utilisateur introuvable."

        stored_hash = row[0].encode("utf-8")
        encrypted = _encrypt_password(password)
        if bcrypt.checkpw(encrypted.encode("utf-8"), stored_hash):
            return True, "Connexion réussie."
        return False, "Mot de passe incorrect."
    except mysql.connector.Error as e:
        return False, format_db_error(e)
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()
