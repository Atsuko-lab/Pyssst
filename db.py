import mysql.connector

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
}
DB_NAME = "pyssst"


def get_connection():
    config = DB_CONFIG.copy()
    config["database"] = DB_NAME
    return mysql.connector.connect(**config)


def format_db_error(e):
    errno = getattr(e, "errno", None)
    if errno == 1049:
        return f"Base '{DB_NAME}' introuvable. Importe pyssst.sql dans phpMyAdmin."
    if errno == 1045:
        return "Accès MySQL refusé. Vérifie user/password."
    if errno in (2003, 2005):
        return "Impossible de joindre MySQL. Vérifie que MySQL est démarré."
    return f"Erreur MySQL: {e}"
