import json
import os
import uuid as uuid_mod
from datetime import datetime, timezone

from services.neon_service import fast_query, write_query, get_pool_status
from services.encryption_service import (
    generate_keypair,
    get_public_key,
    ensure_keypair,
    rotate_key,
    encrypt_payload,
    decrypt_payload,
)
from engines.cache_engine import cache_key, get_cache, set_cache, delete_cache

_ES_COLS = "id, profile_id, peer_profile_id, thread_id, session_type, session_key_id, active, created_at, rotated_at"
_GEK_COLS = "id, group_id, thread_id, key_version, public_key, active, created_at, rotated_at"
_KRE_COLS = "id, profile_id, thread_id, group_id, old_key_version, new_key_version, reason, created_at"

ENCRYPTION_SERVER_SECRET = os.getenv("ENCRYPTION_SERVER_SECRET", "chain-e2ee-default-secret-2024")


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def _get_private_key(profile_id):
    try:
        if _db_available():
            rows = fast_query(
                "SELECT encrypted_private_key FROM chain_encryption_keys WHERE profile_id = %s AND active = TRUE ORDER BY key_version DESC LIMIT 1",
                (profile_id,),
                default=[],
            )
            if rows and rows[0].get("encrypted_private_key"):
                return _decrypt_private_key(rows[0]["encrypted_private_key"], profile_id)
        return None
    except Exception:
        return None


def _encrypt_private_key(private_key_pem, profile_id):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding
    import base64
    key_material = f"{profile_id}:{ENCRYPTION_SERVER_SECRET}"
    aes_key = key_material.encode("utf-8")[:32].ljust(32, b"\0")
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(aes_key), modes.GCM(iv))
    encryptor = cipher.encryptor()
    padder = padding.PKCS7(128).padder()
    padded = padder.update(private_key_pem.encode()) + padder.finalize()
    ct = encryptor.update(padded) + encryptor.finalize()
    return json.dumps({"iv": base64.b64encode(iv).decode(), "ciphertext": base64.b64encode(ct).decode(), "tag": base64.b64encode(encryptor.tag).decode()})


def _decrypt_private_key(encrypted_json, profile_id):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding
    import base64
    data = json.loads(encrypted_json) if isinstance(encrypted_json, str) else encrypted_json
    key_material = f"{profile_id}:{ENCRYPTION_SERVER_SECRET}"
    aes_key = key_material.encode("utf-8")[:32].ljust(32, b"\0")
    iv = base64.b64decode(data["iv"])
    ct = base64.b64decode(data["ciphertext"])
    tag = base64.b64decode(data["tag"])
    cipher = Cipher(algorithms.AES(aes_key), modes.GCM(iv, tag))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ct) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def _row_to_session(row):
    return {
        "id": str(row["id"]),
        "profile_id": str(row["profile_id"]),
        "peer_profile_id": str(row["peer_profile_id"]) if row.get("peer_profile_id") else None,
        "thread_id": str(row["thread_id"]) if row.get("thread_id") else None,
        "session_type": row.get("session_type") or "direct",
        "session_key_id": row.get("session_key_id") or "",
        "active": bool(row.get("active", True)),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "rotated_at": row["rotated_at"].isoformat() if row.get("rotated_at") else None,
    }


def _row_to_group_key(row):
    return {
        "id": str(row["id"]),
        "group_id": str(row["group_id"]) if row.get("group_id") else None,
        "thread_id": str(row["thread_id"]) if row.get("thread_id") else None,
        "key_version": row.get("key_version") or 1,
        "public_key": row.get("public_key") or "",
        "active": bool(row.get("active", True)),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "rotated_at": row["rotated_at"].isoformat() if row.get("rotated_at") else None,
    }


def _row_to_rotation(row):
    return {
        "id": str(row["id"]),
        "profile_id": str(row["profile_id"]) if row.get("profile_id") else None,
        "thread_id": str(row["thread_id"]) if row.get("thread_id") else None,
        "group_id": str(row["group_id"]) if row.get("group_id") else None,
        "old_key_version": row.get("old_key_version") or 0,
        "new_key_version": row.get("new_key_version") or 1,
        "reason": row.get("reason") or "manual",
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def generate_encryption_keys(profile_id):
    if not profile_id:
        return {"ok": False, "error": "profile_id_required"}
    try:
        result = ensure_keypair(profile_id)
        if result and result.get("ok"):
            pk_result = get_public_key(profile_id)
            private_key_pem = result.get("private_key") or result.get("private_key_pem")
            if private_key_pem and _db_available():
                encrypted = _encrypt_private_key(private_key_pem, profile_id)
                write_query(
                    "UPDATE chain_encryption_keys SET encrypted_private_key = %s WHERE profile_id = %s AND active = TRUE",
                    (encrypted, profile_id),
                )
            return {"ok": True, "keypair": pk_result, "has_keys": True, "encryption_enabled": True}
        return {"ok": False, "error": "keygen_failed"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_encryption_keypair(profile_id):
    if not profile_id:
        return {"ok": False, "error": "profile_id_required"}
    try:
        pk = get_public_key(profile_id) if _db_available() else None
        if pk:
            return {"ok": True, "public_key_pem": pk.get("public_key"), "key_version": pk.get("key_version", 1)}
        return {"ok": False, "error": "no_keys"}
    except Exception:
        return {"ok": False, "error": "lookup_failed"}


def ensure_encryption_session(profile_id, peer_profile_id=None, thread_id=None, session_type="direct"):
    if not profile_id:
        return {"ok": False, "error": "profile_id_required"}
    try:
        existing = None
        if _db_available():
            if peer_profile_id:
                rows = fast_query(
                    f"SELECT {_ES_COLS} FROM chain_encrypted_sessions WHERE profile_id = %s AND peer_profile_id = %s AND active = TRUE ORDER BY created_at DESC LIMIT 1",
                    (profile_id, peer_profile_id),
                    default=[],
                )
            elif thread_id:
                rows = fast_query(
                    f"SELECT {_ES_COLS} FROM chain_encrypted_sessions WHERE profile_id = %s AND thread_id = %s AND active = TRUE ORDER BY created_at DESC LIMIT 1",
                    (profile_id, thread_id),
                    default=[],
                )
            else:
                rows = []
            existing = _row_to_session(rows[0]) if rows else None

        if existing:
            return {"ok": True, "session": existing, "created": False}

        session_key_id = str(uuid_mod.uuid4())
        peer_pub_key = None
        if _db_available() and peer_profile_id:
            pk = get_public_key(peer_profile_id)
            if pk:
                peer_pub_key = pk.get("public_key")

        if _db_available():
            write_query(
                "INSERT INTO chain_encrypted_sessions (profile_id, peer_profile_id, thread_id, session_type, session_key_id) VALUES (%s, %s, %s, %s, %s)",
                (profile_id, peer_profile_id, thread_id, session_type, session_key_id),
            )
        return {"ok": True, "session": {
            "id": str(uuid_mod.uuid4()),
            "profile_id": profile_id,
            "peer_profile_id": peer_profile_id,
            "thread_id": thread_id,
            "session_type": session_type,
            "session_key_id": session_key_id,
            "active": True,
        }, "created": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_encryption_session(profile_id, peer_profile_id=None, thread_id=None):
    if not profile_id:
        return None
    try:
        if _db_available():
            if peer_profile_id:
                rows = fast_query(
                    f"SELECT {_ES_COLS} FROM chain_encrypted_sessions WHERE profile_id = %s AND peer_profile_id = %s AND active = TRUE ORDER BY created_at DESC LIMIT 1",
                    (profile_id, peer_profile_id),
                    default=[],
                )
            elif thread_id:
                rows = fast_query(
                    f"SELECT {_ES_COLS} FROM chain_encrypted_sessions WHERE profile_id = %s AND thread_id = %s AND active = TRUE ORDER BY created_at DESC LIMIT 1",
                    (profile_id, thread_id),
                    default=[],
                )
            else:
                return None
            return _row_to_session(rows[0]) if rows else None
        return None
    except Exception:
        return None


def rotate_encryption_session(profile_id, peer_profile_id=None, thread_id=None):
    if not profile_id:
        return {"ok": False, "error": "profile_id_required"}
    try:
        if _db_available():
            if peer_profile_id:
                write_query(
                    "UPDATE chain_encrypted_sessions SET active = FALSE, rotated_at = now() WHERE profile_id = %s AND peer_profile_id = %s AND active = TRUE",
                    (profile_id, peer_profile_id),
                )
            elif thread_id:
                write_query(
                    "UPDATE chain_encrypted_sessions SET active = FALSE, rotated_at = now() WHERE profile_id = %s AND thread_id = %s AND active = TRUE",
                    (profile_id, thread_id),
                )
        result = ensure_encryption_session(profile_id, peer_profile_id=peer_profile_id, thread_id=thread_id)
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


def encrypt_message_payload(plaintext, profile_id, peer_profile_id=None, thread_id=None):
    if not plaintext or not profile_id:
        return {"ok": False, "error": "missing_fields", "plaintext": plaintext}
    try:
        peer_pub_key = None
        if _db_available() and peer_profile_id:
            pk = get_public_key(peer_profile_id)
            if pk:
                peer_pub_key = pk.get("public_key")
        if not peer_pub_key and peer_profile_id:
            return {"ok": False, "error": "peer_public_key_unavailable", "plaintext": plaintext}
        if not peer_pub_key:
            return {"ok": False, "error": "no_public_key", "plaintext": plaintext}
        enc_result = encrypt_payload(plaintext, public_key_pem=peer_pub_key)
        if not enc_result or not enc_result.get("ciphertext"):
            return {"ok": False, "error": "encryption_failed", "plaintext": plaintext}
        return {"ok": True, "encrypted_payload": enc_result, "encryption_version": 1, "fallback_body": "\U0001f512 Encrypted message"}
    except Exception:
        return {"ok": False, "error": "encryption_error", "plaintext": plaintext}


def decrypt_message_payload(encrypted_payload, profile_id):
    if not encrypted_payload or not profile_id:
        return {"ok": False, "error": "missing_fields"}
    try:
        private_key_pem = _get_private_key(profile_id)
        if not private_key_pem:
            return {"ok": False, "error": "private_key_unavailable"}
        decrypted = decrypt_payload(encrypted_payload, private_key_pem.decode() if isinstance(private_key_pem, bytes) else private_key_pem)
        return {"ok": True, "plaintext": decrypted}
    except Exception:
        return {"ok": False, "error": "decryption_failed"}


def encrypt_voice_note_metadata(metadata, profile_id, peer_profile_id=None, thread_id=None):
    metadata_str = json.dumps(metadata) if isinstance(metadata, dict) else str(metadata)
    return encrypt_message_payload(metadata_str, profile_id, peer_profile_id=peer_profile_id, thread_id=thread_id)


def encrypt_media_metadata(metadata, profile_id, peer_profile_id=None, thread_id=None):
    metadata_str = json.dumps(metadata) if isinstance(metadata, dict) else str(metadata)
    return encrypt_message_payload(metadata_str, profile_id, peer_profile_id=peer_profile_id, thread_id=thread_id)


def encrypt_file_metadata(metadata, profile_id, peer_profile_id=None, thread_id=None):
    metadata_str = json.dumps(metadata) if isinstance(metadata, dict) else str(metadata)
    return encrypt_message_payload(metadata_str, profile_id, peer_profile_id=peer_profile_id, thread_id=thread_id)


def encrypt_call_signal(payload, profile_id, peer_profile_id):
    payload_str = json.dumps(payload) if isinstance(payload, dict) else str(payload)
    return encrypt_message_payload(payload_str, profile_id, peer_profile_id=peer_profile_id)


def decrypt_call_signal(encrypted_payload, profile_id):
    return decrypt_message_payload(encrypted_payload, profile_id)


def create_group_encryption_key(group_id=None, thread_id=None, profile_id=None):
    if not group_id and not thread_id:
        return {"ok": False, "error": "group_or_thread_required"}
    try:
        kp = generate_keypair()
        public_key = kp[0]
        key_version = 1
        if _db_available():
            if group_id:
                existing = fast_query(
                    "SELECT COALESCE(MAX(key_version), 0) as mv FROM chain_group_encryption_keys WHERE group_id = %s",
                    (group_id,),
                    default=[{"mv": 0}],
                )
            else:
                existing = fast_query(
                    "SELECT COALESCE(MAX(key_version), 0) as mv FROM chain_group_encryption_keys WHERE thread_id = %s",
                    (thread_id,),
                    default=[{"mv": 0}],
                )
            key_version = (existing[0]["mv"] if existing else 0) + 1
            write_query(
                "INSERT INTO chain_group_encryption_keys (group_id, thread_id, key_version, public_key) VALUES (%s, %s, %s, %s)",
                (group_id, thread_id, key_version, public_key),
            )
        return {"ok": True, "key_version": key_version, "public_key": public_key}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def rotate_group_encryption_key(group_id=None, thread_id=None, reason="participant_left"):
    if not group_id and not thread_id:
        return {"ok": False, "error": "group_or_thread_required"}
    try:
        old_key = get_group_encryption_key(group_id=group_id, thread_id=thread_id)
        old_version = old_key.get("key_version", 0) if old_key else 0
        if _db_available():
            if group_id:
                write_query(
                    "UPDATE chain_group_encryption_keys SET active = FALSE, rotated_at = now() WHERE group_id = %s AND active = TRUE",
                    (group_id,),
                )
            elif thread_id:
                write_query(
                    "UPDATE chain_group_encryption_keys SET active = FALSE, rotated_at = now() WHERE thread_id = %s AND active = TRUE",
                    (thread_id,),
                )
        result = create_group_encryption_key(group_id=group_id, thread_id=thread_id)
        if result.get("ok"):
            record_key_rotation_event(
                profile_id=None, thread_id=thread_id, group_id=group_id,
                old_key_version=old_version, new_key_version=result["key_version"], reason=reason,
            )
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_group_encryption_key(group_id=None, thread_id=None):
    try:
        if _db_available():
            if group_id:
                rows = fast_query(
                    f"SELECT {_GEK_COLS} FROM chain_group_encryption_keys WHERE group_id = %s AND active = TRUE ORDER BY key_version DESC LIMIT 1",
                    (group_id,),
                    default=[],
                )
            elif thread_id:
                rows = fast_query(
                    f"SELECT {_GEK_COLS} FROM chain_group_encryption_keys WHERE thread_id = %s AND active = TRUE ORDER BY key_version DESC LIMIT 1",
                    (thread_id,),
                    default=[],
                )
            else:
                return None
            return _row_to_group_key(rows[0]) if rows else None
        return None
    except Exception:
        return None


def record_key_rotation_event(profile_id=None, thread_id=None, group_id=None, old_key_version=0, new_key_version=1, reason="manual"):
    try:
        if _db_available():
            write_query(
                "INSERT INTO chain_key_rotation_events (profile_id, thread_id, group_id, old_key_version, new_key_version, reason) VALUES (%s, %s, %s, %s, %s, %s)",
                (profile_id, thread_id, group_id, old_key_version, new_key_version, reason),
            )
        return {"ok": True}
    except Exception:
        return {"ok": False}


def is_encryption_enabled_for_thread(thread_id):
    if not thread_id:
        return False
    try:
        cache_hit = get_cache(cache_key("e2ee_thread", thread_id))
        if cache_hit is not None:
            return cache_hit
        enabled = False
        if _db_available():
            rows = fast_query(
                "SELECT is_e2ee FROM chain_message_threads WHERE id = %s LIMIT 1",
                (thread_id,),
                default=[],
            )
            if rows:
                enabled = bool(rows[0].get("is_e2ee", False))
        set_cache(cache_key("e2ee_thread", thread_id), enabled, ttl=300)
        return enabled
    except Exception:
        return False


def mark_message_encrypted(message_id, encrypted_payload=None, encryption_version=1, encryption_session_id=None):
    if not message_id:
        return {"ok": False}
    try:
        if _db_available():
            write_query(
                "UPDATE chain_messages SET encrypted = TRUE, encrypted_payload = %s::jsonb, encryption_version = %s, encryption_session_id = %s WHERE id = %s",
                (json.dumps(encrypted_payload) if encrypted_payload else "{}", encryption_version, encryption_session_id, message_id),
            )
        return {"ok": True}
    except Exception:
        return {"ok": False}


def get_encryption_status(profile_id):
    if not profile_id:
        return {"ok": False, "error": "profile_id_required", "encryption_enabled": False, "has_keys": False}
    try:
        pk = get_public_key(profile_id) if _db_available() else None
        key_version = pk.get("key_version", 0) if pk else 0
        private_key_available = bool(_get_private_key(profile_id))
        has_keys = bool(pk) or private_key_available
        public_key_fingerprint = pk.get("public_key", "")[:48] if pk else ""
        return {
            "ok": True,
            "has_keys": has_keys,
            "encryption_enabled": True,
            "key_version": key_version,
            "public_key_present": bool(pk),
            "private_key_available": private_key_available,
            "public_key_fingerprint": public_key_fingerprint,
            "active_sessions": 0,
        }
    except Exception:
        return {"ok": True, "has_keys": False, "encryption_enabled": False, "key_version": 0, "public_key_present": False, "private_key_available": False}


def get_thread_encryption_status(thread_id):
    if not thread_id:
        return {"ok": False, "error": "thread_id_required"}
    try:
        encrypted = is_encryption_enabled_for_thread(thread_id)
        session = get_encryption_session(None, thread_id=thread_id) if not encrypted else None
        return {"ok": True, "thread_id": thread_id, "encrypted": encrypted, "session": session}
    except Exception:
        return {"ok": False, "error": "status_error"}


def get_group_encryption_status(group_id):
    if not group_id:
        return {"ok": False, "error": "group_id_required"}
    try:
        key = get_group_encryption_key(group_id=group_id)
        return {"ok": True, "group_id": group_id, "encrypted": bool(key), "key_version": key.get("key_version", 0) if key else 0}
    except Exception:
        return {"ok": False, "error": "status_error"}
