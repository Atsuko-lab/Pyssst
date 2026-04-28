# Pyssst — Documentation technique

Messagerie chiffrée de bout en bout développée en Python avec PySide6 et MySQL.

---

## Lancer le projet

```bash
py main.py
```

> MySQL doit être démarré. La base `pyssst` doit être importée via `pyssst.sql` dans phpMyAdmin.  
---

## Structure des fichiers

```
ProjetMessageHach-/
├── main.py              ← point d'entrée
├── db.py                ← connexion à la base de données
├── auth.py              ← inscription, connexion, salage des mots de passe
├── crypto.py            ← génération des clés RSA, chiffrement / déchiffrement
├── messages.py          ← toutes les opérations sur les messages en BDD
├── clé/                 ← clés privées RSA (.pem) de chaque utilisateur
├── ui/
│   ├── login_window.py  ← fenêtre de connexion / inscription
│   └── chat_window.py   ← fenêtre de chat
├── pyssst.sql           ← schéma complet de la base de données
```

---

## `main.py` — Point d'entrée

Lance l'application et affiche la fenêtre de connexion.

### `main()`
Crée l'application PySide6, instancie `LoginWindow` et démarre la boucle d'événements. C'est la seule fonction de ce fichier, appelée via `if __name__ == "__main__"`.

---

## `db.py` — Connexion à la base de données

Centralise la configuration MySQL et la création des connexions.

### `get_connection()`
Retourne une connexion MySQL active à la base `pyssst` en utilisant les paramètres définis dans `DB_CONFIG` (host, user, password).  
Appelée dans tous les fichiers qui ont besoin d'accéder à la BDD.

### `format_db_error(e)`
Prend une exception MySQL et retourne un message d'erreur lisible en français selon le code d'erreur :
- `1049` → base introuvable
- `1045` → accès refusé (mauvais user/password)
- `2003` / `2005` → MySQL non démarré ou inaccessible
- Autre → message brut

---

## `crypto.py` — Clés RSA et chiffrement

Gère tout ce qui touche aux clés et au chiffrement des messages.  
Les clés privées sont stockées dans le dossier `clé/` sous la forme `{pseudo}_private_key.pem`.

### `generate_and_store_keys(username)`
Génère une paire de clés RSA 2048 bits pour un utilisateur :
- Crée la clé privée et la clé publique.
- Sauvegarde la **clé privée** dans `clé/{username}_private_key.pem` (jamais envoyée sur le réseau).
- Retourne le chemin du fichier et la **clé publique** en format PEM (texte), pour la stocker en BDD.

### `load_private_key(username)`
Charge et retourne la clé privée RSA d'un utilisateur depuis son fichier `.pem` local.  
Appelée à l'ouverture de la fenêtre de chat pour pouvoir déchiffrer les messages reçus.

### `encrypt(message, public_key_pem)`
Chiffre un message texte avec la clé publique RSA donnée (format PEM string).  
Utilise le padding **OAEP avec SHA-256** (standard recommandé pour RSA).  
Retourne le message chiffré en bytes.

### `decrypt(ciphertext, private_key)`
Déchiffre un message chiffré (bytes) avec la clé privée RSA.  
Utilise le même padding OAEP SHA-256.  
Retourne le message en texte clair.

---

## `auth.py` — Inscription et connexion

Gère la création de compte et la vérification des identifiants.  
La protection du mot de passe se fait en **deux étapes distinctes** : cryptage puis salage.

```
mot de passe tapé
       ↓
_encrypt_password()  →  HMAC-SHA256 avec clé secrète  (cryptage)
       ↓
_salt_and_hash()     →  bcrypt avec sel aléatoire      (salage)
       ↓
hash final stocké en BDD
```

### `_encrypt_password(password)`
**Étape 1 — Cryptage.**  
Applique un HMAC-SHA256 au mot de passe en utilisant une clé secrète applicative (`PYSSST_SECRET_KEY`).  
Résultat : une empreinte hexadécimale unique qui masque le mot de passe original.  
La clé secrète peut être définie via la variable d'environnement `PYSSST_SECRET_KEY`.

### `_salt_and_hash(encrypted)`
**Étape 2 — Salage.**  
Passe l'empreinte obtenue à `bcrypt.hashpw` avec `bcrypt.gensalt()`.  
bcrypt génère automatiquement un sel **aléatoire et unique** pour chaque utilisateur, puis hache le tout.  
Le sel est intégré dans le hash final stocké en BDD.

### `validate_password_strength(password)`
Vérifie que le mot de passe respecte toutes les règles de sécurité :
- Longueur minimum 8 caractères
- Pas d'espaces
- Au moins une minuscule
- Au moins une majuscule
- Au moins un chiffre
- Au moins un caractère spécial
- Ne contient pas les prénoms "Isham", "Nathan" ou "Fady" (insensible à la casse)

Retourne un tuple `(True, "")` si valide, ou `(False, "message d'erreur")` sinon.

### `register_user(username, password)`
Crée un nouveau compte utilisateur :
1. Vérifie que les champs ne sont pas vides.
2. Appelle `validate_password_strength` pour vérifier le mot de passe.
3. Vérifie que le pseudo n'existe pas déjà en BDD.
4. **Crypte** le mot de passe avec `_encrypt_password` (HMAC-SHA256).
5. **Sale et hache** le résultat avec `_salt_and_hash` (bcrypt + sel aléatoire).
6. Génère une paire de clés RSA avec `generate_and_store_keys`.
6. Insère l'utilisateur en BDD avec le hash et la clé publique.

Retourne `(True, message)` ou `(False, message_erreur)`.

### `login_user(username, password)`
Vérifie les identifiants d'un utilisateur :
1. Vérifie que les champs ne sont pas vides.
2. Récupère le hash stocké en BDD pour ce pseudo.
3. **Crypte** le mot de passe saisi avec `_encrypt_password` (même opération qu'à l'inscription).
4. Compare l'empreinte obtenue avec le hash stocké via `bcrypt.checkpw`.

Retourne `(True, "Connexion réussie.")` ou `(False, message_erreur)`.

---

## `messages.py` — Gestion des messages en BDD

Contient toutes les fonctions qui lisent ou modifient la table `messages`.

### `get_all_users(exclude)`
Retourne la liste de tous les pseudos enregistrés en BDD, **sauf** l'utilisateur passé en paramètre.  
Utilisé pour remplir la liste des contacts dans le chat.

### `get_public_key(username)`
Récupère et retourne la clé publique RSA (format PEM string) d'un utilisateur depuis la BDD.  
Utilisée pour chiffrer un message avant de l'envoyer à cet utilisateur.

### `save_message(expediteur, destinataire, chiffre_dest, chiffre_exp)`
Insère un nouveau message en BDD avec deux versions chiffrées :
- `chiffre_dest` : le message chiffré avec la clé publique du **destinataire** (pour qu'il puisse le lire).
- `chiffre_exp` : le même message chiffré avec la clé publique de l'**expéditeur** (pour qu'il puisse relire ses propres messages).

### `mark_messages_as_read(viewer, sender)`
Passe à `lu = 1` tous les messages envoyés par `sender` à `viewer` qui n'avaient pas encore été lus.  
Appelée dès qu'un utilisateur ouvre une conversation.

### `get_unread_count(viewer, sender)`
Retourne le nombre de messages non lus envoyés par `sender` à `viewer`.  
Utilisée pour afficher le badge 🔴 dans la liste des contacts.

### `update_message(msg_id, expediteur, chiffre_dest, chiffre_exp)`
Modifie le contenu d'un message existant (identifié par `msg_id`).  
Met à jour les deux versions chiffrées et enregistre la date de modification (`modifie_le`).  
Vérifie que l'expéditeur est bien l'auteur du message et qu'il n'a pas été supprimé pour tous.  
Retourne `True` si la modification a eu lieu, `False` sinon.

### `delete_message_for_me(msg_id, expediteur)`
Cache un message uniquement pour l'expéditeur en passant `cache_par_expediteur = 1`.  
Le destinataire peut toujours voir le message.  
Retourne `True` si la suppression a eu lieu, `False` sinon.

### `delete_message_for_everyone(msg_id, expediteur)`
Supprime un message pour tout le monde : passe `supprime_pour_tous = 1` et efface le contenu chiffré.  
Le message disparaît des deux côtés.  
Retourne `True` si la suppression a eu lieu, `False` sinon.

### `fetch_messages(viewer, other_user)`
Récupère tous les messages entre `viewer` et `other_user`, dans les deux sens.  
Filtre :
- Les messages supprimés pour tous.
- Les messages cachés pour le viewer (supprimé uniquement pour lui).

Retourne une liste de tuples : `(id, expediteur, destinataire, chiffre_dest, chiffre_exp, envoye_le, modifie_le, lu)`.

---

## `ui/login_window.py` — Fenêtre de connexion

Interface graphique de la page d'accueil. Thème sombre Catppuccin Mocha.

### `LoginWindow` (classe)
Fenêtre fixe 400×440 px avec un formulaire centré dans une carte arrondie.

#### `__init__(self)`
Construit l'interface : titre, sous-titre, champ pseudo, champ mot de passe (masqué), bouton "Se connecter" et bouton "Créer un compte".  
La touche **Entrée** dans le champ mot de passe déclenche la connexion.

#### `login(self)`
Récupère les valeurs des champs et appelle `login_user`.  
Si succès → ouvre `ChatWindow` et ferme la fenêtre de login.  
Si échec → affiche une boîte d'alerte avec le message d'erreur.

#### `register(self)`
Récupère les valeurs des champs et appelle `register_user`.  
Affiche un message de succès ou d'erreur selon le résultat.

---

## `ui/chat_window.py` — Fenêtre de chat

Interface principale du chat. Divisée en panneau gauche (liste des contacts) et panneau droit (conversation + saisie).

### `MessageBubble` (classe)
Widget graphique représentant une seule bulle de message.

#### `__init__(self, msg_id, expediteur, texte, heure, sent_by_me, modifie, lu, on_edit, on_delete)`
Construit la bulle visuellement :
- Mes messages : alignés à **droite**, fond violet foncé `#4c3f77`.
- Messages reçus : alignés à **gauche**, fond gris `#313244`, avec le nom de l'expéditeur en bleu.
- Affiche l'heure et " · modifié" si le message a été édité.
- Affiche `✓` (gris) si non lu, `✓✓` (bleu) si lu — uniquement sur mes messages.
- Si c'est mon message : ajoute les boutons "Modifier" et "Supprimer".

---

### `ChatWindow` (classe)
Fenêtre principale du chat, redimensionnable (minimum 600×400).

#### `__init__(self, username)`
Initialise la fenêtre, charge la clé privée de l'utilisateur, construit l'interface (panneau gauche + panneau droit), remplit la liste des contacts et démarre un timer qui rafraîchit les messages toutes les **2 secondes**.

#### `refresh_users(self)`
Vide et recharge la liste des contacts depuis la BDD.  
Pour chaque contact, récupère le nombre de messages non lus et affiche un badge 🔴 si > 0.

#### `on_user_click(self, item)`
Appelée quand on clique sur un contact.  
Met à jour le contact sélectionné, marque ses messages comme lus, charge la conversation et met le focus sur le champ de saisie.

#### `clear_messages(self)`
Supprime tous les widgets de bulles du panneau de messages (nettoyage avant rechargement).

#### `load_messages(self)`
Récupère les messages de la conversation en cours depuis la BDD et crée une bulle pour chacun.  
Enregistre la "signature" de la conversation (nombre de messages, dernier id, dernière modification, état lu) pour détecter les changements lors du polling.  
Fait défiler automatiquement vers le bas.

#### `_add_bubble(self, row)`
Déchiffre un message (en utilisant la clé privée de l'utilisateur connecté) et crée un widget `MessageBubble`.  
Si le déchiffrement échoue, affiche `[illisible]`.

#### `_scroll_to_bottom(self)`
Fait défiler la zone de messages jusqu'en bas après un court délai (pour laisser Qt finir le rendu).

#### `_compute_signature(self, rows)`
Calcule un tuple résumant l'état actuel de la conversation : `(nombre, dernier_id, dernière_modification, état_lu)`.  
Utilisé pour savoir si un rechargement est nécessaire sans interroger la BDD en permanence.

#### `send_message(self)`
Envoie un message :
1. Vérifie qu'un destinataire est sélectionné et que le champ n'est pas vide.
2. Chiffre le message deux fois : une avec la clé publique du destinataire, une avec la sienne.
3. Sauvegarde en BDD et recharge la conversation.

#### `edit_message(self, msg_id, ancien_texte)`
Ouvre une boîte de dialogue pour modifier le texte d'un message.  
Rechiffre le nouveau texte pour les deux parties et met à jour en BDD.

#### `delete_message(self, msg_id)`
Ouvre une boîte de dialogue avec le choix :
- **"Pour moi"** → cache le message uniquement pour l'expéditeur.
- **"Pour tout le monde"** → supprime le message pour les deux côtés.

#### `poll(self)`
Appelée automatiquement toutes les 2 secondes par le timer.  
Rafraîchit la liste des contacts (pour mettre à jour les badges non lus), puis vérifie si la conversation en cours a changé (nouveaux messages, modification, état lu). Si oui, recharge les bulles.

---

## Base de données — `pyssst.sql`

### Table `users`
| Colonne | Type | Description |
|---|---|---|
| `pseudo` | varchar(100) | Identifiant unique, clé primaire |
| `motdepasseHASH` | varchar(255) | Hash bcrypt du mot de passe salé |
| `cléPublic` | text | Clé publique RSA au format PEM |

### Table `messages`
| Colonne | Type | Description |
|---|---|---|
| `id` | int | Identifiant auto-incrémenté |
| `expediteur` | varchar(100) | Pseudo de l'expéditeur |
| `destinataire` | varchar(100) | Pseudo du destinataire |
| `contenu_chiffre_dest` | mediumblob | Message chiffré avec la clé publique du destinataire |
| `contenu_chiffre_exp` | mediumblob | Message chiffré avec la clé publique de l'expéditeur |
| `envoye_le` | datetime | Date/heure d'envoi (automatique) |
| `modifie_le` | datetime | Date/heure de modification (null si jamais modifié) |
| `supprime_pour_tous` | tinyint(1) | 1 = supprimé pour tout le monde |
| `supprime_le` | datetime | Date de suppression globale |
| `cache_par_expediteur` | tinyint(1) | 1 = caché uniquement pour l'expéditeur |
| `cache_par_destinataire` | tinyint(1) | 1 = caché uniquement pour le destinataire |
| `lu` | tinyint(1) | 0 = non lu, 1 = lu par le destinataire |

---

## Bibliothèques utilisées

| Bibliothèque | Rôle |
|---|---|
| `PySide6` | Interface graphique |
| `mysql-connector-python` | Connexion à la base MySQL |
| `cryptography` | Génération des clés RSA, chiffrement OAEP |
| `bcrypt` | Salage + hachage des mots de passe |
| `hmac` | Cryptage HMAC-SHA256 des mots de passe |
| `hashlib` | Digestmod SHA-256 pour le HMAC |
| `re` | Expressions régulières (validation du mot de passe) |
| `os` | Lecture de la variable d'environnement `PYSSST_SECRET_KEY` |
| `pathlib` | Gestion des chemins de fichiers (clés .pem) |
