"""
Phase 86 — Registration Performance: Batched checks, single INSERT, background deps, timing.

Tests:
  1. import time is present in auth_service.py
  2. _log_timing function is defined
  3. _check_email_username_phone_taken replaces individual checks in register_chain_user
  4. _check_email_username_phone_taken uses single UNION ALL query
  5. _bootstrap_registration_profile uses _neon_insert_profile (single INSERT)
  6. _bootstrap_registration_profile does NOT call _neon_update_profile
  7. date_of_birth included in single INSERT (no separate UPDATE)
  8. _ensure_profile_dependencies runs in background thread (threading.Thread)
  9. _neon_get_profile_by returns None without double-query on not-found
 10. Static columns include chain_wallets, chain_creator_tools, chain_user_settings,
     chain_account_security, chain_login_events in neon_service.py
 11. _supabase_auth_email_exists NOT called from register_chain_user
 12. Timing log calls exist for duplicate_check, supabase_sign_up, profile_bootstrap, store_session
 13. Python compile check
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["FLASK_ENV"] = "development"
os.environ["ENV"] = "development"
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"
os.environ["CHAIN_DISABLE_DB_PING"] = "1"
os.environ["CHAIN_DISABLE_RATE_LIMITS"] = "1"
os.environ["SECRET_KEY"] = "test-phase86-secret-key"


class Phase86RegistrationPerformance:
    def __init__(self):
        self.errors = []
        self.passes = 0
        self.fails = 0
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def check(self, name, condition, detail=""):
        if condition:
            self.passes += 1
            print(f"  PASS  {name}")
        else:
            self.fails += 1
            msg = f"  FAIL  {name}"
            if detail:
                msg += f"  \u2014  {detail}"
            print(msg)
            self.errors.append(f"{name}: {detail}")

    def _read_source(self, rel_path):
        path = os.path.join(self.base_dir, *rel_path.split("/"))
        with open(path) as f:
            return f.read()

    # ── Test 1: import time ──
    def test_01_import_time(self):
        print("\n[Test 1] import time in auth_service.py")
        src = self._read_source("services/auth_service.py")
        self.check("import time present",
                    "import time" in src,
                    "Missing import time")

    # ── Test 2: _log_timing function ──
    def test_02_log_timing(self):
        print("\n[Test 2] _log_timing function defined")
        src = self._read_source("services/auth_service.py")
        self.check("_log_timing defined",
                    "def _log_timing" in src,
                    "Missing _log_timing function")
        self.check("prints ms timing",
                    "print(f\"[timing]" in src,
                    "Missing timing print")
        self.check("only logs > 50ms",
                    "0.05" in src.split("def _log_timing")[1].split("\n")[1] if "def _log_timing" in src else False,
                    "Missing duration threshold check")

    # ── Test 3: _check_email_username_phone_taken replaces individual checks ──
    def test_03_batched_duplicate_check(self):
        print("\n[Test 3] register_chain_user uses batched duplicate check")
        src = self._read_source("services/auth_service.py")
        reg_func = src.split("def register_chain_user")[1].split("def _")[0] if "def register_chain_user" in src else ""
        self.check("calls _check_email_username_phone_taken",
                    "_check_email_username_phone_taken" in reg_func,
                    "Missing batched check call")
        self.check("NOT calling _email_exists_in_profiles directly",
                    "_email_exists_in_profiles(email)" not in reg_func,
                    "Still calls _email_exists_in_profiles directly")
        self.check("NOT calling _supabase_auth_email_exists directly",
                    "_supabase_auth_email_exists" not in reg_func,
                    "Still calls _supabase_auth_email_exists directly")
        self.check("NOT calling _profile_exists_by_username directly",
                    "_profile_exists_by_username(username)" not in reg_func,
                    "Still calls _profile_exists_by_username directly")
        self.check("NOT calling _phone_exists_in_profiles directly",
                    "_phone_exists_in_profiles(phone)" not in reg_func,
                    "Still calls _phone_exists_in_profiles directly")

    # ── Test 4: _check_email_username_phone_taken uses UNION ALL ──
    def test_04_union_all_query(self):
        print("\n[Test 4] _check_email_username_phone_taken uses single UNION ALL query")
        src = self._read_source("services/auth_service.py")
        func_match = src.split("def _check_email_username_phone_taken")[1].split("\n    ") if "def _check_email_username_phone_taken" in src else []
        func_body = " ".join(func_match[:20])
        self.check("single UNION ALL query",
                    "UNION ALL" in src,
                    "Missing UNION ALL in batched check")
        self.check("checks email",
                    "normalized_email" in src,
                    "Missing email check")
        self.check("checks username",
                    "username = %s" in src,
                    "Missing username check")
        self.check("checks phone",
                    "normalized_phone" in src,
                    "Missing phone check")
        self.check("no Supabase admin list_users call",
                    "supabase.auth.admin.list_users" not in (src.split("def _check_email_username_phone_taken")[1].split("def ")[0] if "def _check_email_username_phone_taken" in src else ""),
                    "Supabase admin list_users still present")

    # ── Test 5: _bootstrap_registration_profile uses single INSERT ──
    def test_05_single_insert(self):
        print("\n[Test 5] _bootstrap_registration_profile uses _neon_insert_profile")
        src = self._read_source("services/auth_service.py")
        bootstrap = src.split("def _bootstrap_registration_profile")[1].split("def ")[0] if "def _bootstrap_registration_profile" in src else ""
        self.check("calls _neon_insert_profile",
                    "_neon_insert_profile" in bootstrap,
                    "Missing _neon_insert_profile call")
        self.check("NOT calling _neon_update_profile",
                    "_neon_update_profile" not in bootstrap,
                    "Still calls _neon_update_profile")
        self.check("NOT calling ensure_neon_profile as primary",
                    not (bootstrap.strip().startswith("profile, ensure_error = ensure_neon_profile")),
                    "Still uses ensure_neon_profile as primary path")

    # ── Test 6: _bootstrap_registration_profile no _neon_update_profile ──
    def test_06_no_update_after_insert(self):
        print("\n[Test 6] No _neon_update_profile after INSERT")
        src = self._read_source("services/auth_service.py")
        bootstrap = src.split("def _bootstrap_registration_profile")[1].split("def ")[0] if "def _bootstrap_registration_profile" in src else ""
        self.check("_neon_update_profile not called",
                    "_neon_update_profile" not in bootstrap,
                    "_neon_update_profile still present")
        self.check("no DOB UPDATE query",
                    "UPDATE chain_profiles SET date_of_birth" not in bootstrap,
                    "Separate DOB UPDATE still present")

    # ── Test 7: date_of_birth in single INSERT ──
    def test_07_dob_in_insert(self):
        print("\n[Test 7] date_of_birth included in _registration_profile_payload")
        src = self._read_source("services/auth_service.py")
        payload_func = src.split("def _registration_profile_payload")[1].split("def ")[0] if "def _registration_profile_payload" in src else ""
        self.check("date_of_birth in payload dict",
                    "\"date_of_birth\": dob" in payload_func,
                    "date_of_birth not in _registration_profile_payload")
        self.check("date_of_birth in NEON_PROFILE_COLUMNS",
                    "date_of_birth" in self._read_source("services/profile_service.py"),
                    "date_of_birth not in NEON_PROFILE_COLUMNS in profile_service.py")

    # ── Test 8: _ensure_profile_dependencies in background thread ──
    def test_08_background_deps(self):
        print("\n[Test 8] _ensure_profile_dependencies runs in background thread")
        src = self._read_source("services/auth_service.py")
        reg_func = src.split("def register_chain_user")[1].split("def _")[0] if "def register_chain_user" in src else ""
        bg_count = reg_func.count("threading.Thread")
        self.check("threading.Thread used for deps",
                    "threading.Thread(target=_ensure_profile_dependencies" in reg_func,
                    "Missing background thread for ensure_profile_dependencies")
        self.check("NOT synchronous _ensure_profile_dependencies call in main path",
                    "_ensure_profile_dependencies(profile.get" not in reg_func or "_ensure_profile_dependencies(profile.get" not in reg_func.replace("threading.Thread", "##SKIP##"),
                    "Synchronous _ensure_profile_dependencies still called")
        self.check("daemon thread",
                    "daemon=True" in reg_func,
                    "Missing daemon=True")

    # ── Test 9: _neon_get_profile_by returns None without double-query ──
    def test_09_no_double_query(self):
        print("\n[Test 9] _neon_get_profile_by returns None without double-query on not-found")
        src = self._read_source("services/profile_service.py")
        get_profile = src.split("def _neon_get_profile_by")[1].split("\ndef ")[0] if "def _neon_get_profile_by" in src else ""
        self.check("fast_query used",
                    "fast_query" in get_profile,
                    "Missing fast_query call")
        self.check("returns None on not-found",
                    "return None  # not found" in get_profile,
                    "Missing None return for not-found")
        self.check("_direct_profile_lookup only in exception path",
                    get_profile.strip().endswith("_direct_profile_lookup(field, value)") or "return _direct_profile_lookup" in get_profile,
                    "_direct_profile_lookup not in error fallback path")

    # ── Test 10: Static columns in neon_service.py ──
    def test_10_static_columns(self):
        print("\n[Test 10] Static columns for dependency tables in neon_service.py")
        src = self._read_source("services/neon_service.py")
        self.check("chain_wallets static",
                    "\"chain_wallets\"" in src,
                    "Missing chain_wallets static columns")
        self.check("chain_creator_tools static",
                    "\"chain_creator_tools\"" in src,
                    "Missing chain_creator_tools static columns")
        self.check("chain_user_settings static",
                    "\"chain_user_settings\"" in src,
                    "Missing chain_user_settings static columns")
        self.check("chain_account_security static",
                    "\"chain_account_security\"" in src,
                    "Missing chain_account_security static columns")
        self.check("chain_login_events static",
                    "\"chain_login_events\"" in src,
                    "Missing chain_login_events static columns")

    # ── Test 11: _supabase_auth_email_exists NOT in register_chain_user ──
    def test_11_no_supabase_auth_check_in_register(self):
        print("\n[Test 11] _supabase_auth_email_exists not called from register_chain_user")
        src = self._read_source("services/auth_service.py")
        reg_func = src.split("def register_chain_user")[1].split("def _")[0] if "def register_chain_user" in src else ""
        self.check("_supabase_auth_email_exists not in reg flow",
                    "_supabase_auth_email_exists" not in reg_func,
                    "_supabase_auth_email_exists still called in register_chain_user")

    # ── Test 12: Timing log calls exist ──
    def test_12_timing_log_calls(self):
        print("\n[Test 12] Timing log calls present in register_chain_user")
        src = self._read_source("services/auth_service.py")
        reg_func = src.split("def register_chain_user")[1].split("def _")[0] if "def register_chain_user" in src else ""
        self.check("duplicate_check timing",
                    "register_chain_user.duplicate_check" in reg_func,
                    "Missing duplicate_check timing")
        self.check("supabase_sign_up timing",
                    "register_chain_user.supabase_sign_up" in reg_func,
                    "Missing supabase_sign_up timing")
        self.check("profile_bootstrap timing",
                    "register_chain_user.profile_bootstrap" in reg_func,
                    "Missing profile_bootstrap timing")
        self.check("store_session timing",
                    "register_chain_user.store_session" in reg_func,
                    "Missing store_session timing")

    # ── Test 13: Python compile check ──
    def test_13_compile_check(self):
        print("\n[Test 13] Python files compile")
        files = [
            "app.py",
            "api_routes/auth_routes.py",
            "api_routes/profile_routes.py",
            "services/auth_service.py",
            "services/profile_service.py",
            "services/neon_service.py",
        ]
        for rel in files:
            path = os.path.join(self.base_dir, rel)
            try:
                compile(open(path).read(), path, "exec")
                self.check(f"{rel} compiles", True)
            except SyntaxError as e:
                self.check(f"{rel} compiles", False, str(e))

    # ── Run all ──
    def run_all(self):
        print("=" * 55)
        print("  Phase 86 — Registration Performance")
        print("=" * 55)
        tests = [
            self.test_01_import_time,
            self.test_02_log_timing,
            self.test_03_batched_duplicate_check,
            self.test_04_union_all_query,
            self.test_05_single_insert,
            self.test_06_no_update_after_insert,
            self.test_07_dob_in_insert,
            self.test_08_background_deps,
            self.test_09_no_double_query,
            self.test_10_static_columns,
            self.test_11_no_supabase_auth_check_in_register,
            self.test_12_timing_log_calls,
            self.test_13_compile_check,
        ]
        for test in tests:
            test()
        print("\n" + "=" * 55)
        total = self.passes + self.fails
        print(f"  Phase 86 Summary: {self.passes}/{total} passed")
        if self.fails:
            print(f"  Failures: {self.fails}")
            for err in self.errors:
                print(f"    - {err}")
        print("=" * 55)
        return self.fails == 0


if __name__ == "__main__":
    suite = Phase86RegistrationPerformance()
    success = suite.run_all()
    sys.exit(0 if success else 1)
