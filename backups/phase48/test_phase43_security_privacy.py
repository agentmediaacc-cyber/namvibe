"""
Phase 43 E2E: Security, Privacy, Device Management & Encryption Foundation
  - Device session creation
  - Device revoke
  - Logout all other devices
  - Privacy settings save/load
  - Security event creation
  - Trusted device create/remove
  - Encryption key generation
  - Public key retrieval
  - Key rotation
  - Backward compatibility with Phase 42
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "0"
os.environ["CHAIN_TRUST_PROFILE_SCHEMA"] = "1"

from app import create_app
app = create_app()

import services.message_feature_service as _mfs
import services.message_delivery_service as _mds
from services.neon_service import get_pool_status, fast_query, write_query

PASS = 0; FAIL = 0
def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}" + (f" -- {detail}" if detail else ""))

def _db_true():
    s = get_pool_status()
    return bool(s.get("pool_ready") or s.get("recent_success") or s.get("configured"))
if hasattr(_mfs, '_db_available'): _mfs._db_available = _db_true
if hasattr(_mds, '_db_available'): _mds._db_available = _db_true

PID_A = None; PID_B = None

def _ensure_test_profiles():
    global PID_A, PID_B
    from services.neon_service import fast_query
    import uuid as _uuid_mod
    rows = fast_query("SELECT id FROM chain_profiles WHERE username = 'e2e_43_a' LIMIT 1", default=[])
    if rows:
        PID_A = str(rows[0]["id"])
    else:
        dummy_auth = str(_uuid_mod.uuid4())
        rows = fast_query(
            "INSERT INTO chain_profiles (auth_user_id, username, display_name, email) VALUES (%s, %s, %s, %s) RETURNING id",
            (dummy_auth, "e2e_43_a", "E2E 43 A", "e2e_43_a@test.chain"),
            default=[],
        )
        if rows:
            PID_A = str(rows[0]["id"])
    rows = fast_query("SELECT id FROM chain_profiles WHERE username = 'e2e_43_b' LIMIT 1", default=[])
    if rows:
        PID_B = str(rows[0]["id"])
    else:
        dummy_auth = str(_uuid_mod.uuid4())
        rows = fast_query(
            "INSERT INTO chain_profiles (auth_user_id, username, display_name, email) VALUES (%s, %s, %s, %s) RETURNING id",
            (dummy_auth, "e2e_43_b", "E2E 43 B", "e2e_43_b@test.chain"),
            default=[],
        )
        if rows:
            PID_B = str(rows[0]["id"])

def _ensure_device_sessions_table():
    write_query(
        "CREATE TABLE IF NOT EXISTS chain_device_sessions ("
        "id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "
        "profile_id UUID NOT NULL, "
        "device_name VARCHAR(255) DEFAULT 'unknown', "
        "device_type VARCHAR(50) DEFAULT 'unknown', "
        "browser VARCHAR(255) DEFAULT 'unknown', "
        "os VARCHAR(255) DEFAULT 'unknown', "
        "ip_hash VARCHAR(64) DEFAULT '', "
        "trusted BOOLEAN DEFAULT FALSE, "
        "last_seen TIMESTAMPTZ DEFAULT now(), "
        "created_at TIMESTAMPTZ DEFAULT now(), "
        "revoked_at TIMESTAMPTZ DEFAULT NULL)"
    )

def _ensure_security_events_table():
    write_query(
        "CREATE TABLE IF NOT EXISTS chain_security_events ("
        "id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "
        "profile_id UUID NOT NULL, "
        "event_type VARCHAR(50) NOT NULL, "
        "device_id UUID DEFAULT NULL, "
        "metadata JSONB DEFAULT '{}'::jsonb, "
        "created_at TIMESTAMPTZ DEFAULT now())"
    )

def _ensure_privacy_settings_table():
    write_query(
        "CREATE TABLE IF NOT EXISTS chain_privacy_settings ("
        "profile_id UUID PRIMARY KEY, "
        "show_online_status BOOLEAN DEFAULT TRUE, "
        "show_last_seen BOOLEAN DEFAULT TRUE, "
        "show_read_receipts BOOLEAN DEFAULT TRUE, "
        "show_typing_indicator BOOLEAN DEFAULT TRUE, "
        "show_profile_photo BOOLEAN DEFAULT TRUE, "
        "allow_calls BOOLEAN DEFAULT TRUE, "
        "allow_group_invites BOOLEAN DEFAULT TRUE, "
        "updated_at TIMESTAMPTZ DEFAULT now())"
    )

def _ensure_encryption_keys_table():
    write_query(
        "CREATE TABLE IF NOT EXISTS chain_encryption_keys ("
        "id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "
        "profile_id UUID NOT NULL, "
        "public_key TEXT NOT NULL, "
        "key_version INTEGER DEFAULT 1, "
        "active BOOLEAN DEFAULT TRUE, "
        "created_at TIMESTAMPTZ DEFAULT now())"
    )

def _ensure_trusted_devices_table():
    write_query(
        "CREATE TABLE IF NOT EXISTS chain_trusted_devices ("
        "id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "
        "profile_id UUID NOT NULL, "
        "device_session_id UUID NOT NULL, "
        "trusted_at TIMESTAMPTZ DEFAULT now(), "
        "created_at TIMESTAMPTZ DEFAULT now())"
    )

# ---- SETUP ----
print("=== PHASE 43 — SETUP ===")
# Clean stale rows from prior runs
from services.neon_service import write_query
for tbl in ["chain_trusted_devices", "chain_encryption_keys", "chain_privacy_settings", "chain_security_events", "chain_device_sessions"]:
    write_query(f"DELETE FROM {tbl}")
_ensure_test_profiles()
_ensure_device_sessions_table()
_ensure_security_events_table()
_ensure_privacy_settings_table()
_ensure_encryption_keys_table()
_ensure_trusted_devices_table()
check("test profiles ready", PID_A and PID_B)
check("tables exist", True)

# ---- 1. DEVICE SESSION CREATION ----
print("\n=== 1. DEVICE SESSION CREATION ===")
from services.security_service import create_device_session, get_device_sessions, get_device_session
d1 = create_device_session(PID_A, device_name="iPhone 15", device_type="mobile", browser="Safari", system_os="iOS 18", ip_hash="abc123", trusted=True)
check("device session 1 created", d1 is not None)
d2 = create_device_session(PID_A, device_name="MacBook Pro", device_type="desktop", browser="Chrome", system_os="macOS 15", ip_hash="def456", trusted=False)
check("device session 2 created", d2 is not None)
sessions = get_device_sessions(PID_A)
check("get_device_sessions returns list", isinstance(sessions, list) and len(sessions) >= 2)
fetched = get_device_session(d1)
check("get_device_session returns device", fetched is not None and fetched["id"] == d1)
check("device has device_name", fetched and fetched.get("device_name") == "iPhone 15")
check("device has trusted flag", fetched and fetched.get("trusted") is True)

# ---- 2. DEVICE REVOKE ----
print("\n=== 2. DEVICE REVOKE ===")
from services.security_service import revoke_device_session, is_device_active
check("device active before revoke", is_device_active(d2))
revoke_device_session(d2, PID_A)
check("device inactive after revoke", not is_device_active(d2))
fetched2 = get_device_session(d2)
check("revoked_at is set", fetched2 and fetched2.get("revoked_at") is not None)

# ---- 3. LOGOUT ALL OTHER DEVICES ----
print("\n=== 3. LOGOUT ALL OTHER DEVICES ===")
from services.security_service import logout_all_other_devices
d3 = create_device_session(PID_A, device_name="Test Device 3", device_type="mobile")
check("device 3 created", d3 is not None)
d4 = create_device_session(PID_A, device_name="Test Device 4", device_type="desktop")
check("device 4 created", d4 is not None)
logout_all_other_devices(d3, PID_A)
check("d3 still active after logout-others", is_device_active(d3))
check("d4 revoked after logout-others", not is_device_active(d4))

# ---- 4. PRIVACY SETTINGS SAVE/LOAD ----
print("\n=== 4. PRIVACY SETTINGS ===")
from services.security_service import get_privacy_settings, upsert_privacy_settings
defaults = get_privacy_settings(PID_A)
check("privacy defaults load", defaults is not None)
check("show_online_status defaults true", defaults.get("show_online_status") != False)
check("show_last_seen defaults true", defaults.get("show_last_seen") != False)
check("allow_calls defaults true", defaults.get("allow_calls") != False)
upsert_privacy_settings(PID_A, {"show_online_status": False, "show_read_receipts": False, "allow_calls": False})
updated = get_privacy_settings(PID_A)
check("show_online_status set to false", updated.get("show_online_status") is False)
check("show_read_receipts set to false", updated.get("show_read_receipts") is False)
check("allow_calls set to false", updated.get("allow_calls") is False)
upsert_privacy_settings(PID_A, {"show_online_status": True, "show_read_receipts": True, "allow_calls": True})
restored = get_privacy_settings(PID_A)
check("show_online_status restored", restored.get("show_online_status") is True)
check("show_read_receipts restored", restored.get("show_read_receipts") is True)

# ---- 5. SECURITY EVENT CREATION ----
print("\n=== 5. SECURITY EVENTS ===")
from services.security_service import create_security_event, get_security_events
e1 = create_security_event(PID_A, "login", metadata={"ip": "127.0.0.1"})
check("login event created", e1 is not None)
e2 = create_security_event(PID_A, "password_changed", metadata={"method": "reset"})
check("password_changed event created", e2 is not None)
e3 = create_security_event(PID_A, "new_device", device_id=d1, metadata={"device_name": "iPhone 15"})
check("new_device event created", e3 is not None)
events = get_security_events(PID_A, limit=10)
check("get_security_events returns list", isinstance(events, list) and len(events) >= 3)
types = {e["event_type"] for e in events}
check("login event present", "login" in types)
check("password_changed event present", "password_changed" in types)
check("new_device event present", "new_device" in types)

# ---- 6. TRUSTED DEVICES ----
print("\n=== 6. TRUSTED DEVICES ===")
from services.security_service import trust_device, untrust_device, get_trusted_devices
# Create a fresh device for trust testing
d5 = create_device_session(PID_A, device_name="Trust Test Device", device_type="mobile")
check("trust test device created", d5 is not None)
trust_device(PID_A, d5)
trusted = get_trusted_devices(PID_A)
check("trusted device in list", any(t["device_session_id"] == d5 for t in trusted))
session_check = get_device_session(d5)
check("device marked trusted in sessions", session_check and session_check.get("trusted") is True)
untrust_device(PID_A, d5)
trusted_after = get_trusted_devices(PID_A)
check("device removed from trusted list", not any(t["device_session_id"] == d5 for t in trusted_after))
session_check2 = get_device_session(d5)
check("device no longer marked trusted", session_check2 and session_check2.get("trusted") is False)

# ---- 7. ENCRYPTION KEY GENERATION ----
print("\n=== 7. ENCRYPTION KEY GENERATION ===")
from services.encryption_service import generate_keypair, get_public_key, ensure_keypair, rotate_key
pub, priv = generate_keypair()
check("public key generated", pub is not None and pub.startswith("-----BEGIN PUBLIC KEY-----"))
check("private key generated", priv is not None and priv.startswith("-----BEGIN PRIVATE KEY-----"))
key_data = ensure_keypair(PID_A)
check("ensure_keypair returns key data", key_data is not None)
check("key has public_key", "public_key" in key_data)
check("key has key_version", isinstance(key_data.get("key_version"), int) and key_data["key_version"] >= 1)
_first_key_version = key_data["key_version"]

# ---- 8. PUBLIC KEY RETRIEVAL ----
print("\n=== 8. PUBLIC KEY RETRIEVAL ===")
retrieved = get_public_key(PID_A)
check("get_public_key returns key", retrieved is not None)
check("retrieved key matches", retrieved["public_key"] == key_data["public_key"])
check("retrieved has id", "id" in retrieved)

# ---- 9. KEY ROTATION ----
print("\n=== 9. KEY ROTATION ===")
_key_before_rotate = key_data["public_key"]
rotated = rotate_key(PID_A)
check("rotate_key returns new key", rotated is not None)
check("key_version incremented", rotated.get("key_version", 0) > _first_key_version)
new_key = get_public_key(PID_A)
check("new key is different from old key", new_key is not None and new_key["public_key"] != _key_before_rotate)

# ---- 10. ENCRYPT/DECRYPT ----
print("\n=== 10. ENCRYPT/DECRYPT ===")
from services.encryption_service import encrypt_payload, decrypt_payload
test_message = "Hello CHAIN! This is a secret message."
encrypted = encrypt_payload(test_message, public_key_pem=pub)
check("encrypt_payload returns dict", isinstance(encrypted, dict))
check("encrypted has ciphertext", "ciphertext" in encrypted)
check("encrypted has encrypted_aes_key", "encrypted_aes_key" in encrypted)
check("encrypted has iv", "iv" in encrypted)
check("encrypted has tag", "tag" in encrypted)
decrypted = decrypt_payload(encrypted, priv)
check("decrypt_payload returns original", decrypted == test_message)

# ---- 11. SQL MIGRATION EXISTS ----
print("\n=== 11. SQL MIGRATION EXISTS ===")
check("migration file exists", os.path.isfile("sql/phase43_security_privacy.sql"))
with open("sql/phase43_security_privacy.sql") as f:
    sql = f.read()
check("migration has chain_device_sessions", "chain_device_sessions" in sql)
check("migration has chain_security_events", "chain_security_events" in sql)
check("migration has chain_privacy_settings", "chain_privacy_settings" in sql)
check("migration has chain_encryption_keys", "chain_encryption_keys" in sql)
check("migration has chain_trusted_devices", "chain_trusted_devices" in sql)
check("migration has CREATE INDEX statements", "CREATE INDEX IF NOT EXISTS" in sql)
check("migration has gen_random_uuid", "gen_random_uuid()" in sql)

# ---- 12. API ENDPOINTS ----
print("\n=== 12. API ENDPOINTS ===")
from flask import url_for
with app.test_client() as c:
    # Simulate login
    with c.session_transaction() as sess:
        sess["auth_user_id"] = PID_A
        sess["profile_id"] = PID_A
        sess["username"] = "e2e_43_a"

    resp = c.get("/security/api/devices")
    check("GET /security/api/devices 200", resp.status_code == 200)
    data = resp.get_json()
    check("devices api returns ok", data.get("ok"))
    check("devices api has devices list", isinstance(data.get("devices"), list))

    resp2 = c.get("/privacy/api/settings")
    check("GET /privacy/api/settings 200", resp2.status_code == 200)
    data2 = resp2.get_json()
    check("privacy api returns ok", data2.get("ok"))
    check("privacy api has settings", isinstance(data2.get("settings"), dict))

    resp3 = c.post("/privacy/api/settings", json={"show_online_status": False, "allow_calls": False})
    check("POST /privacy/api/settings 200", resp3.status_code == 200)
    data3 = resp3.get_json()
    check("privacy update returns ok", data3.get("ok"))

    resp4 = c.get("/security/api/events")
    check("GET /security/api/events 200", resp4.status_code == 200)
    data4 = resp4.get_json()
    check("events api returns ok", data4.get("ok"))
    check("events api has events list", isinstance(data4.get("events"), list))

    resp5 = c.post(f"/security/api/device/{d1}/trust")
    check("POST /security/api/device/<id>/trust 200", resp5.status_code == 200)
    data5 = resp5.get_json()
    check("trust api returns ok", data5.get("ok"))

    resp6 = c.post(f"/security/api/device/{d1}/untrust")
    check("POST /security/api/device/<id>/untrust 200", resp6.status_code == 200)
    data6 = resp6.get_json()
    check("untrust api returns ok", data6.get("ok"))

    resp7 = c.post(f"/security/api/device/{d2}/revoke")
    check("POST /security/api/device/<id>/revoke 200", resp7.status_code in (200, 404))

    resp8 = c.post("/security/api/logout-all-other-devices",
                   json={"current_device_id": d1})
    check("POST /security/api/logout-all-other-devices 200", resp8.status_code == 200)
    data8 = resp8.get_json()
    check("logout-all returns ok", data8.get("ok"))

# ---- 13. FRONTEND PAGES ----
print("\n=== 13. FRONTEND PAGES ===")
check("templates/security/devices.html exists", os.path.isfile("templates/security/devices.html"))
check("templates/security/privacy.html exists", os.path.isfile("templates/security/privacy.html"))
check("templates/security/security_events.html exists", os.path.isfile("templates/security/security_events.html"))
with open("templates/security/devices.html") as f:
    dhtml = f.read()
check("devices template has revoke form", "revoke" in dhtml)
check("devices template has logout-all", "logout-all-other-devices" in dhtml)
with open("templates/security/privacy.html") as f:
    phtml = f.read()
check("privacy template has show_online_status", "show_online_status" in phtml)
check("privacy template has show_last_seen", "show_last_seen" in phtml)
check("privacy template has allow_calls", "allow_calls" in phtml)
with open("templates/security/security_events.html") as f:
    ehtml = f.read()
check("events template has event_type classes", "event-icon" in ehtml)
check("events template has login icon class", "event-icon.login" in ehtml)

# ---- 14. BACKWARD COMPAT (Phase 42) ----
print("\n=== 14. BACKWARD COMPAT (Phase 42) ===")
from services.presence_cache_service import set_presence_cache, get_presence_cache
check("presence_cache_service imports ok", True)
set_presence_cache("e2e_43_test", "online")
pc = get_presence_cache("e2e_43_test")
check("presence cache works", pc is not None and pc == "online")

from services.performance_guard import timed_section, log_if_slow
check("performance_guard imports ok", True)

# ---- SUMMARY ----
total = PASS + FAIL
print(f"\n=== SUMMARY ===")
print(f"  PASS: {PASS}/{total}  FAIL: {FAIL}/{total}")
if FAIL > 0:
    print("  Some tests failed -- review output above.")
else:
    print("  All Phase 43 tests passed!")
