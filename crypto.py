from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding

KEY_DIR = Path(__file__).resolve().parent / "clé"
KEY_DIR.mkdir(exist_ok=True)


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

    private_key_path = KEY_DIR / f"{username}_private_key.pem"
    with open(private_key_path, "wb") as key_file:
        key_file.write(private_key_pem)

    return str(private_key_path), public_key_pem.decode("utf-8")


def load_private_key(username):
    key_path = KEY_DIR / f"{username}_private_key.pem"
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
