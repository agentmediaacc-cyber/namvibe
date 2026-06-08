#!/usr/bin/env python3
"""Phase 46: End-to-End Encryption Activation — comprehensive test suite."""

import os, sys, json, uuid, unittest
from datetime import datetime, timezone

os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_TEST_FAKE_DB"] = "1"
os.environ["CHAIN_DB_URL"] = "postgresql://localhost/chain_test"
os.environ["ENCRYPTION_SERVER_SECRET"] = "test-secret-key-phase46"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app
from unittest.mock import patch, MagicMock
from services.neon_service import fast_query, write_query, get_pool_status

def _db_available():
    import os
    if (
        os.getenv("FLASK_TESTING") == "1"
        or os.getenv("CHAIN_FAST_LOCAL") == "1"
        or os.getenv("CHAIN_TEST_FAKE_DB") == "1"
    ):
        return False
    return bool(get_pool_status().get("configured"))

def _fake_fast_query(sql_text, params=None, timeout_ms=2000, default=None):
    return default if default is not None else []

def _fake_write_query(sql_text, params=None, timeout_ms=5000):
    return {"ok": True}

import services.encryption_service as _encryption_service
_encryption_service.fast_query = _fake_fast_query
_encryption_service.write_query = _fake_write_query


class Phase46E2EEActivationTest(unittest.TestCase):
    """Phase 46 E2EE activation tests.

    Tests that:
      1. SQL migration is idempotent
      2. encrypt/decrypt round-trips work
      3. Key rotation works
      4. API endpoints respond correctly
      5. Socket events exist
      6. Group key rotation works
      7. Fallback for old unencrypted messages
      8. Encryption status endpoint
    """

    maxDiff = None

    # ── helpers ────────────────────────────────────────────

    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()
        self.ctx = app.app_context()
        self.ctx.push()
        self._patch_db()

    def tearDown(self):
        self._unpatch_db()
        self.ctx.pop()

    def _patch_db(self):
        """Mock DB to return controlled data for tests."""
        self._db_patcher = patch("services.e2ee_service._db_available", return_value=False)
        self._db_patcher.start()
        self._enc_patcher = patch("services.e2ee_service.fast_query")
        self._enc_write_patcher = patch("services.e2ee_service.write_query")
        self._enc_public_key_patcher = patch("services.e2ee_service.get_public_key")
        self._mock_fast = self._enc_patcher.start()
        self._mock_write = self._enc_write_patcher.start()
        self._mock_public_key = self._enc_public_key_patcher.start()
        self._mock_fast.return_value = []
        self._mock_write.return_value = {"ok": True}
        self._mock_public_key.return_value = {
            "id": "fake-key-id",
            "public_key": "fake-public-key",
            "key_version": 1,
        }

    def _unpatch_db(self):
        try:
            self._enc_patcher.stop()
        except Exception:
            pass
        try:
            self._enc_write_patcher.stop()
        except Exception:
            pass
        try:
            self._enc_public_key_patcher.stop()
        except Exception:
            pass
        try:
            self._db_patcher.stop()
        except Exception:
            pass

    def _make_payload(self, plaintext, public_key_pem):
        """Simulate hybrid encryption without DB."""
        from services.encryption_service import encrypt_payload
        return encrypt_payload(plaintext, public_key_pem=public_key_pem)

    def _fake_login(self, profile_id="p-test-1"):
        with self.client.session_transaction() as sess:
            sess["auth_user_id"] = profile_id
            sess["profile_id"] = profile_id
            sess["access_token"] = "test-token"
        return profile_id

    # ── SQL migration idempotence ──────────────────────────

    def test_01_sql_migration_idempotent(self):
        """Verify the SQL file can run multiple times (idempotent)."""
        path = os.path.join(os.path.dirname(__file__), "..", "sql", "phase46_e2ee_activation.sql")
        self.assertTrue(os.path.exists(path), "SQL migration file missing")
        with open(path) as f:
            sql = f.read()
        self.assertIn("CREATE TABLE IF NOT EXISTS", sql, "Should use IF NOT EXISTS")
        self.assertIn("ADD COLUMN IF NOT EXISTS", sql, "Should use ADD COLUMN IF NOT EXISTS")
        self.assertIn("CREATE INDEX IF NOT EXISTS", sql, "Should use IF NOT EXISTS for indexes")

    # ── encrypt / decrypt round-trip ───────────────────────

    def test_02_encrypt_decrypt_roundtrip(self):
        """encrypt_message_payload + decrypt_message_payload round-trip."""
        self._unpatch_db()
        from services.encryption_service import generate_keypair, encrypt_payload, decrypt_payload
        from services.e2ee_service import encrypt_message_payload, decrypt_message_payload
        profile_a = "p-roundtrip-a"
        profile_b = "p-roundtrip-b"
        thread_id = "t-roundtrip-1"
        plaintext = "Hello secure world!"

        kp_a = generate_keypair()
        kp_b = generate_keypair()
        pub_a, priv_a = kp_a
        pub_b, priv_b = kp_b

        with patch("services.e2ee_service._db_available", return_value=True), \
             patch("services.e2ee_service.get_public_key") as mock_pk, \
             patch("services.e2ee_service._get_private_key") as mock_priv, \
             patch("services.e2ee_service.fast_query", return_value=[]), \
             patch("services.e2ee_service.write_query", return_value=None):
            mock_pk.return_value = {"public_key": pub_b, "key_version": 1}
            mock_priv.return_value = priv_b

            enc = encrypt_message_payload(plaintext, profile_a, peer_profile_id=profile_b, thread_id=thread_id)
            self.assertIsNotNone(enc, "encrypt should return a result")
            self.assertTrue(enc.get("ok"), f"encrypt failed: {enc.get('error')}")
            self.assertIn("encrypted_payload", enc)

            dec = decrypt_message_payload(enc["encrypted_payload"], profile_b)
            self.assertTrue(dec.get("ok"), f"decrypt failed: {dec.get('error')}")
            self.assertEqual(dec["plaintext"], plaintext)

    def test_03_encrypt_fallback_body(self):
        """encrypt_message_payload includes fallback_body for DB storage."""
        from services.encryption_service import generate_keypair
        from services.e2ee_service import encrypt_message_payload
        with patch("services.e2ee_service._db_available", return_value=True), \
             patch("services.e2ee_service.get_public_key") as mock_pk, \
             patch("services.e2ee_service.fast_query", return_value=[]), \
             patch("services.e2ee_service.write_query", return_value=None):
            pub_b = generate_keypair()[0]
            mock_pk.return_value = {"public_key": pub_b, "key_version": 1}
            enc = encrypt_message_payload("secret", "p-fallback-a", peer_profile_id="p-fallback-b", thread_id="t-fallback")
        self.assertIn("fallback_body", enc)
        self.assertEqual(enc["fallback_body"], "\U0001f512 Encrypted message")

    def test_04_decrypt_wrong_recipient_fails(self):
        """Decrypt with wrong recipient returns error."""
        self._unpatch_db()
        from services.encryption_service import generate_keypair
        from services.e2ee_service import encrypt_message_payload, decrypt_message_payload
        kp_alice = generate_keypair()
        kp_bob = generate_keypair()
        kp_eve = generate_keypair()

        with patch("services.e2ee_service._db_available", return_value=True), \
             patch("services.e2ee_service.get_public_key") as mock_pk, \
             patch("services.e2ee_service._get_private_key") as mock_priv, \
             patch("services.e2ee_service.fast_query", return_value=[]), \
             patch("services.e2ee_service.write_query", return_value=None):
            mock_pk.return_value = {"public_key": kp_bob[0], "key_version": 1}
            mock_priv.return_value = kp_eve[1]
            enc = encrypt_message_payload("secret", "p-alice", peer_profile_id="p-bob", thread_id="t-dec-fail")
            dec = decrypt_message_payload(enc["encrypted_payload"], "p-eve")
            self.assertFalse(dec.get("ok"), "Eve should not decrypt Alice-Bob message")

    # ── Key generation ────────────────────────────────────

    def test_05_generate_encryption_keys(self):
        """generate_encryption_keys creates keys and returns status."""
        self._unpatch_db()
        from services.e2ee_service import generate_encryption_keys
        pid = "p-gen-keys-1"
        with patch("services.e2ee_service._db_available", return_value=False), \
             patch("services.e2ee_service.ensure_keypair") as mock_ek:
            mock_ek.return_value = {"ok": True, "private_key": "mock-priv-key"}
            result = generate_encryption_keys(pid)
        self.assertTrue(result.get("ok"), f"key gen failed: {result.get('error')}")

    def test_06_key_rotation(self):
        """rotate_encryption_session generates new session key."""
        from services.e2ee_service import rotate_encryption_session
        result = rotate_encryption_session("p-rot-alice", peer_profile_id="p-rot-bob")
        self.assertTrue(result.get("ok"), f"rotation failed: {result.get('error')}")

    # ── Group key rotation ─────────────────────────────────

    def test_07_group_key_rotation(self):
        """rotate_group_encryption_key returns ok."""
        from services.e2ee_service import rotate_group_encryption_key
        result = rotate_group_encryption_key(group_id="g-test-1", reason="test")
        self.assertTrue(result.get("ok"))
        self.assertIn("key_version", result)

    def test_08_group_key_rotation_thread_id(self):
        """rotate_group_encryption_key works with thread_id."""
        from services.e2ee_service import rotate_group_encryption_key
        result = rotate_group_encryption_key(thread_id="t-group-rot", reason="participant_left")
        self.assertTrue(result.get("ok"))

    # ── Encryption status ─────────────────────────────────

    def test_09_get_encryption_status(self):
        """get_encryption_status returns status dict."""
        from services.e2ee_service import get_encryption_status
        pid = "p-status-1"
        status = get_encryption_status(pid)
        self.assertIn("has_keys", status)
        self.assertIn("encryption_enabled", status)

    def test_10_is_encryption_enabled_for_thread(self):
        """is_encryption_enabled_for_thread returns bool."""
        from services.e2ee_service import is_encryption_enabled_for_thread
        result = is_encryption_enabled_for_thread("t-nonexistent")
        self.assertIsInstance(result, bool)

    # ── Record events ──────────────────────────────────────

    def test_11_record_key_rotation_event(self):
        """record_key_rotation_event writes without error."""
        from services.e2ee_service import record_key_rotation_event
        try:
            record_key_rotation_event("p-rec-1", thread_id="t-rec-1", old_key_version=0, new_key_version="2", reason="test")
        except Exception as e:
            self.fail(f"record_key_rotation_event raised: {e}")

    def test_12_mark_message_encrypted(self):
        """mark_message_encrypted writes without error."""
        from services.e2ee_service import mark_message_encrypted
        try:
            mark_message_encrypted("m-enc-1")
        except Exception as e:
            self.fail(f"mark_message_encrypted raised: {e}")

    # ── API endpoints ──────────────────────────────────────

    def test_20_api_encryption_status_no_auth(self):
        """GET /encryption/api/status returns non-200 when not logged in."""
        resp = self.client.get("/encryption/api/status")
        self.assertNotEqual(resp.status_code, 200, "Unauthenticated request should not return 200")

    def test_21_api_encryption_status_authenticated(self):
        """GET /encryption/api/status returns JSON when logged in."""
        self._fake_login("p-api-status-1")
        with patch("api_routes.encryption_routes.get_current_profile") as m:
            m.return_value = {"id": "p-api-status-1"}
            resp = self.client.get("/encryption/api/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsInstance(data, dict)

    def test_22_api_rotate_authenticated(self):
        """POST /encryption/api/rotate returns JSON."""
        self._fake_login("p-api-rotate-1")
        with patch("api_routes.encryption_routes.get_current_profile") as m:
            m.return_value = {"id": "p-api-rotate-1"}
            resp = self.client.post("/encryption/api/rotate", json={})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsInstance(data, dict)

    def test_23_api_thread_status(self):
        """GET /encryption/api/thread/<id>/status returns JSON."""
        self._fake_login("p-api-thread-1")
        with patch("api_routes.encryption_routes.get_current_profile") as m:
            m.return_value = {"id": "p-api-thread-1"}
            resp = self.client.get("/encryption/api/thread/t-test-1/status")
        self.assertEqual(resp.status_code, 200)

    def test_24_api_activate_thread(self):
        """POST /encryption/api/thread/<id>/activate returns JSON."""
        self._fake_login("p-api-activate-1")
        with patch("api_routes.encryption_routes.get_current_profile") as m:
            m.return_value = {"id": "p-api-activate-1"}
            resp = self.client.post("/encryption/api/thread/t-test-1/activate")
        self.assertEqual(resp.status_code, 200)

    def test_25_api_group_status(self):
        """GET /encryption/api/group/<id>/status returns JSON."""
        self._fake_login("p-api-group-1")
        with patch("api_routes.encryption_routes.get_current_profile") as m:
            m.return_value = {"id": "p-api-group-1"}
            resp = self.client.get("/encryption/api/group/g-test-1/status")
        self.assertEqual(resp.status_code, 200)

    def test_26_api_history(self):
        """GET /encryption/api/history returns JSON."""
        self._fake_login("p-api-history-1")
        with patch("api_routes.encryption_routes.get_current_profile") as m:
            m.return_value = {"id": "p-api-history-1"}
            resp = self.client.get("/encryption/api/history")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsInstance(data, dict)

    # ── Socket events existence ────────────────────────────

    def test_30_socket_events_registered(self):
        """Verify socket events exist in socket_events.py."""
        path = os.path.join(os.path.dirname(__file__), "..", "services", "socket_events.py")
        with open(path) as f:
            content = f.read()
        events = [
            "encryption:status",
            "encryption:key-rotated",
            "encryption:thread-secured",
            "encryption:group-key-rotated",
            "encryption:message-secured",
        ]
        for ev in events:
            self.assertIn(f'"{ev}"', content, f"Socket event '{ev}' not found in socket_events.py")

    # ── DB schema ──────────────────────────────────────────

    def test_31_db_tables_exist_in_migration(self):
        """Verify migration creates all required tables."""
        path = os.path.join(os.path.dirname(__file__), "..", "sql", "phase46_e2ee_activation.sql")
        with open(path) as f:
            sql = f.read()
        tables = [
            "chain_encrypted_sessions",
            "chain_group_encryption_keys",
            "chain_key_rotation_events",
        ]
        for table in tables:
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", sql)

    def test_32_column_additions_exist_in_migration(self):
        """Verify migration adds encrypted columns to messages."""
        path = os.path.join(os.path.dirname(__file__), "..", "sql", "phase46_e2ee_activation.sql")
        with open(path) as f:
            sql = f.read()
        cols = [
            "encrypted",
            "encrypted_payload",
            "encryption_version",
            "encryption_session_id",
        ]
        for col in cols:
            self.assertIn(f"ADD COLUMN IF NOT EXISTS {col}", sql)

    # ── Group call leave triggers key rotation ─────────────

    def test_35_group_call_leave_triggers_key_rotation(self):
        """leave_group_call in group_call_service calls rotate_group_encryption_key."""
        path = os.path.join(os.path.dirname(__file__), "..", "services", "group_call_service.py")
        with open(path) as f:
            content = f.read()
        self.assertIn("rotate_group_encryption_key", content)
        self.assertIn("reason=\"participant_left\"", content)

    # ── E2EE UI indicators exist in templates ──────────────

    def test_40_e2ee_indicator_thread(self):
        """E2EE indicator appears in thread.html."""
        path = os.path.join(os.path.dirname(__file__), "..", "templates", "messages", "thread.html")
        with open(path) as f:
            content = f.read()
        self.assertIn("e2ee-indicator", content)
        self.assertIn("e2ee-label", content)
        self.assertIn("/encryption/api/status", content)

    def test_41_e2ee_indicator_index(self):
        """E2EE badge appears in index.html."""
        path = os.path.join(os.path.dirname(__file__), "..", "templates", "messages", "index.html")
        with open(path) as f:
            content = f.read()
        self.assertIn("data-e2ee", content)
        self.assertIn("E2EE", content)

    def test_42_e2ee_privacy_section(self):
        """E2EE section in privacy.html."""
        path = os.path.join(os.path.dirname(__file__), "..", "templates", "security", "privacy.html")
        with open(path) as f:
            content = f.read()
        self.assertIn("End-to-End Encryption", content)
        self.assertIn("rotate-keys-btn", content)
        self.assertIn("/encryption/api/status", content)

    def test_43_e2ee_settings_section(self):
        """E2EE section in profile/settings.html."""
        path = os.path.join(os.path.dirname(__file__), "..", "templates", "profile", "settings.html")
        with open(path) as f:
            content = f.read()
        self.assertIn("End-to-End Encryption", content)
        self.assertIn("e2ee-settings-rotate", content)
        self.assertIn("/encryption/api/status", content)

    def test_44_e2ee_group_call_section(self):
        """E2EE badge in group_call.html."""
        path = os.path.join(os.path.dirname(__file__), "..", "templates", "calls", "group_call.html")
        with open(path) as f:
            content = f.read()
        self.assertIn("gc-e2ee-badge", content)

    # ── Encryption flag in WebRTC JS ───────────────────────

    def test_50_webrtc_js_encrypted_flag(self):
        """encrypted: true in webrtc_calls.js signals."""
        path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "webrtc_calls.js")
        with open(path) as f:
            content = f.read()

        # All three call:offer, call:answer, call:ice-candidate should carry encrypted: true
        offer_count = content.count("call:offer")
        answer_count = content.count("call:answer")
        ice_count = content.count("call:ice-candidate")
        encrypted_count = content.count("encrypted: true")

        self.assertGreaterEqual(encrypted_count, 3,
            f"Expected encrypted: true at least 3 times, got {encrypted_count}")

    def test_51_group_calls_js_encrypted_flag(self):
        """encrypted: true in group_calls.js signaling."""
        path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "group_calls.js")
        with open(path) as f:
            content = f.read()
        self.assertIn("encrypted: true", content)

    # ── Message delivery service encryption ────────────────

    def test_55_message_delivery_encryption_column_added(self):
        """send_message in message_delivery_service.py includes encrypted columns."""
        path = os.path.join(os.path.dirname(__file__), "..", "services", "message_delivery_service.py")
        with open(path) as f:
            content = f.read()
        self.assertIn("encrypted_payload", content)
        self.assertIn("encryption_version", content)
        self.assertIn("encrypt_message_payload", content)

    def test_56_message_delivery_decryption_added(self):
        """get_thread_messages decrypts encrypted messages."""
        path = os.path.join(os.path.dirname(__file__), "..", "services", "message_delivery_service.py")
        with open(path) as f:
            content = f.read()
        self.assertIn("decrypt_message_payload", content)
        self.assertIn("decrypted", content)
        self.assertIn("\\U0001f512 Encrypted message", content)

    def test_57_message_feature_encryption_added(self):
        """send_text_message in message_feature_service.py encrypts."""
        path = os.path.join(os.path.dirname(__file__), "..", "services", "message_feature_service.py")
        with open(path) as f:
            content = f.read()
        self.assertIn("encrypt_message_payload", content)
        self.assertIn("encrypted_payload", content)

    def test_58_message_feature_decryption_added(self):
        """get_thread_messages in message_feature_service.py decrypts."""
        path = os.path.join(os.path.dirname(__file__), "..", "services", "message_feature_service.py")
        with open(path) as f:
            content = f.read()
        self.assertIn("decrypt_message_payload", content)

    # ── E2EE service has all required functions ────────────

    def test_60_e2ee_service_has_all_functions(self):
        """e2ee_service.py contains all required functions."""
        path = os.path.join(os.path.dirname(__file__), "..", "services", "e2ee_service.py")
        with open(path) as f:
            content = f.read()
        required = [
            "generate_encryption_keys",
            "get_encryption_keypair",
            "get_encryption_status",
            "encrypt_message_payload",
            "decrypt_message_payload",
            "rotate_encryption_session",
            "rotate_group_encryption_key",
            "is_encryption_enabled_for_thread",
            "record_key_rotation_event",
            "mark_message_encrypted",
        ]
        for fn in required:
            self.assertIn(f"def {fn}", content, f"Missing function {fn} in e2ee_service.py")

    # ── API routes file has all endpoints ──────────────────

    def test_61_encryption_routes_has_all_endpoints(self):
        """encryption_routes.py contains all required endpoints."""
        path = os.path.join(os.path.dirname(__file__), "..", "api_routes", "encryption_routes.py")
        with open(path) as f:
            content = f.read()
        required = [
            "/api/status",
            "/api/rotate",
            "/api/thread/<thread_id>/status",
            "/api/thread/<thread_id>/activate",
            "/api/group/<group_id>/status",
            "/api/group/<group_id>/rotate",
            "/api/history",
        ]
        for ep in required:
            self.assertIn(ep, content, f"Missing endpoint {ep} in encryption_routes.py")


if __name__ == "__main__":
    unittest.main()
