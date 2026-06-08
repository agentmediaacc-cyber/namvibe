import os
import base64
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from services.neon_service import fast_query, write_query
from services.logging_service import log_error

_KEY_SIZE = 2048


def generate_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=_KEY_SIZE)
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    return public_pem, private_pem


def get_public_key(profile_id):
    rows = fast_query(
        "SELECT id, public_key, key_version FROM chain_encryption_keys "
        "WHERE profile_id = %s AND active = TRUE ORDER BY key_version DESC LIMIT 1",
        (profile_id,),
        default=[],
    )
    if rows:
        return {"id": str(rows[0]["id"]), "public_key": rows[0]["public_key"], "key_version": rows[0]["key_version"]}
    return None


def ensure_keypair(profile_id):
    existing = get_public_key(profile_id)
    if existing:
        return existing
    return rotate_key(profile_id)


def rotate_key(profile_id):
    public_pem, _ = generate_keypair()
    current = fast_query(
        "SELECT COALESCE(MAX(key_version), 0) as max_ver FROM chain_encryption_keys WHERE profile_id = %s",
        (profile_id,),
        default=[],
    )
    next_version = (current[0]["max_ver"] + 1) if current else 1
    write_query("UPDATE chain_encryption_keys SET active = FALSE WHERE profile_id = %s", (profile_id,))
    write_query(
        "INSERT INTO chain_encryption_keys (profile_id, public_key, key_version, active) VALUES (%s, %s, %s, TRUE)",
        (profile_id, public_pem, next_version),
    )
    return get_public_key(profile_id)


def encrypt_payload(plaintext, public_key_pem=None, profile_id=None):
    if public_key_pem is None and profile_id is not None:
        key_data = get_public_key(profile_id)
        if not key_data:
            raise ValueError("No public key found for profile")
        public_key_pem = key_data["public_key"]
    if not public_key_pem:
        raise ValueError("public_key_pem or profile_id required")
    public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    aes_key = os.urandom(32)
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(aes_key), modes.GCM(iv))
    encryptor = cipher.encryptor()
    if isinstance(plaintext, str):
        plaintext = plaintext.encode("utf-8")
    ciphertext = encryptor.update(plaintext) + encryptor.finalize()
    encrypted_aes_key = public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return {
        "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
        "encrypted_aes_key": base64.b64encode(encrypted_aes_key).decode("utf-8"),
        "iv": base64.b64encode(iv).decode("utf-8"),
        "tag": base64.b64encode(encryptor.tag).decode("utf-8"),
    }


def decrypt_payload(encrypted_payload, private_key_pem):
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"), password=None
    )
    aes_key = private_key.decrypt(
        base64.b64decode(encrypted_payload["encrypted_aes_key"]),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    cipher = Cipher(
        algorithms.AES(aes_key),
        modes.GCM(
            base64.b64decode(encrypted_payload["iv"]),
            base64.b64decode(encrypted_payload["tag"]),
        ),
    )
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(base64.b64decode(encrypted_payload["ciphertext"])) + decryptor.finalize()
    return plaintext.decode("utf-8")
