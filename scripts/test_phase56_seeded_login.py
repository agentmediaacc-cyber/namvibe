"""
Phase 56: Test Seeded Login — End-to-end verification that test users can log in.
"""
import os, sys, json, uuid as uuid_mod
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_TEST_FAKE_DB"] = "1"
os.environ["CHAIN_TRUST_PROFILE_SCHEMA"] = "1"

from app import create_app
app = create_app()
app.config["WTF_CSRF_ENABLED"] = False
app.config["CSRF_ENABLED"] = False

PASS = 0; FAIL = 0
def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {label}"); PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else "")); FAIL += 1

TEST_USERS = ["chain_star", "chain_moon", "chain_gold", "chain_million", "chain_premium"]
PASSWORD = "Adimintest"

# ============================================================
# TASK 1: Seed script exists
# ============================================================
def test_seed_script_exists():
    check("seed_chain_test_users.py exists",
          os.path.isfile("scripts/seed_chain_test_users.py"))

# ============================================================
# TASK 2: Run seed idempotently
# ============================================================
def test_run_seed():
    import subprocess
    result = subprocess.run(
        [sys.executable, "scripts/seed_chain_test_users.py"],
        capture_output=True, text=True, timeout=120
    )
    ok = result.returncode == 0
    check("Seed script runs successfully (exit 0)", ok,
          f"stderr={result.stderr[:200]}" if not ok else None)

def test_seed_idempotent():
    import subprocess
    result1 = subprocess.run(
        [sys.executable, "scripts/seed_chain_test_users.py"],
        capture_output=True, text=True, timeout=120
    )
    result2 = subprocess.run(
        [sys.executable, "scripts/seed_chain_test_users.py"],
        capture_output=True, text=True, timeout=120
    )
    check("Seed is idempotent (no crash on second run)",
          result2.returncode == 0,
          f"stderr={result2.stderr[:200]}" if result2.returncode != 0 else None)

# ============================================================
# TASK 3: All 5 auth records exist in chain_profiles
# ============================================================
def test_profiles_exist():
    from services.neon_service import fast_query
    for username in TEST_USERS:
        rows = fast_query(
            "SELECT id, auth_user_id, username, email FROM chain_profiles WHERE username = %s LIMIT 1",
            (username,), default=[]
        )
        check(f"Profile exists: {username}",
              bool(rows) and rows[0].get("auth_user_id") is not None,
              detail=f"rows={rows}")

# ============================================================
# TASK 4: Login succeeds with username + password
# ============================================================
def test_login_by_username():
    with app.test_request_context():
        app.config["SECRET_KEY"] = "test_secret"
        from services.auth_service import login_chain_user
        ok, result = login_chain_user("chain_star", PASSWORD)
        # Should succeed via dev credential fallback (since user not in Supabase Auth)
        check("Login by username succeeds", ok,
              detail=result if not ok else None)
        check("Login redirects to /profile/", result == "/profile/",
              detail=str(result))

def test_login_by_email():
    with app.test_request_context():
        app.config["SECRET_KEY"] = "test_secret"
        from services.auth_service import login_chain_user
        ok, result = login_chain_user("chain_star@chain.local", PASSWORD)
        check("Login by email succeeds", ok,
              detail=result if not ok else None)

# ============================================================
# TASK 5: Wrong password fails
# ============================================================
def test_login_wrong_password():
    with app.test_request_context():
        app.config["SECRET_KEY"] = "test_secret"
        from services.auth_service import login_chain_user
        ok, result = login_chain_user("chain_star", "wrong_password_123")
        check("Wrong password fails", not ok,
              detail="Login succeeded with wrong password!" if ok else None)

# ============================================================
# TASK 6: chain_star has 4 confirmed friends
# ============================================================
def test_friend_follows():
    from services.neon_service import fast_query
    star_rows = fast_query(
        "SELECT id FROM chain_profiles WHERE username = 'chain_star' LIMIT 1",
        default=[]
    )
    if not star_rows:
        check("chain_star profile found for friend check", False)
        return
    star_id = star_rows[0]["id"]
    follow_rows = fast_query(
        """SELECT cf.id, cp.username FROM chain_follows cf
           JOIN chain_profiles cp ON cp.id = cf.following_profile_id
           WHERE cf.follower_profile_id = %s""",
        (star_id,), default=[]
    )
    check("chain_star follows 4+ users",
          len(follow_rows) >= 4,
          detail=f"found {len(follow_rows)} follows: {[r['username'] for r in follow_rows]}")
    follower_rows = fast_query(
        """SELECT cf.id, cp.username FROM chain_follows cf
           JOIN chain_profiles cp ON cp.id = cf.follower_profile_id
           WHERE cf.following_profile_id = %s""",
        (star_id,), default=[]
    )
    check("4+ users follow chain_star back",
          len(follower_rows) >= 4,
          detail=f"found {len(follower_rows)} followers: {[r['username'] for r in follower_rows]}")
    mutual = [r["username"] for r in follow_rows
              if r["username"] in {fr["username"] for fr in follower_rows}]
    check("chain_star has 4+ mutual friends",
          len(mutual) >= 4,
          detail=f"mutual: {mutual}")

# ============================================================
# TASK 7: /messages/api/friends returns seeded friends after login
# ============================================================
def test_friends_api_after_login():
    with app.app_context():
        app.config["SECRET_KEY"] = "test_secret"
        with app.test_request_context():
            from flask import session
            from services.auth_service import login_chain_user
            ok, result = login_chain_user("chain_star", PASSWORD)
            if not ok:
                check("Login before friends API test", False,
                      detail=f"Login failed: {result}")
                return
        with app.test_client() as client:
            # Re-login via test client to set session cookies
            resp = client.post("/auth/login", data={
                "login_id": "chain_star", "password": PASSWORD
            }, follow_redirects=False)
            check("Login via POST /auth/login", resp.status_code in (302, 200),
                  detail=f"status={resp.status_code}")
            friends_resp = client.get("/messages/api/friends")
            check("/messages/api/friends returns 200",
                  friends_resp.status_code == 200,
                  detail=f"status={friends_resp.status_code}")
            if friends_resp.status_code == 200:
                data = friends_resp.get_json()
                friends_list = data.get("friends", []) if isinstance(data, dict) else (data or [])
                usernames = [f.get("username") for f in friends_list if f.get("username")]
                for friend_username in ["chain_moon", "chain_gold", "chain_million", "chain_premium"]:
                    check(f"friend list includes {friend_username}",
                          friend_username in usernames,
                          detail=f"got {usernames}")

# ============================================================
# TASK 8: Browser-equivalent login (POST /auth/login flow)
# ============================================================
def test_browser_login_username():
    """Exact flow: browser POSTs login_id + password to /auth/login"""
    with app.test_client() as client:
        resp = client.post("/auth/login", data={
            "login_id": "chain_star", "password": PASSWORD
        }, follow_redirects=False)
        check("Browser login by username redirects (302)", resp.status_code == 302,
              detail=f"status={resp.status_code}")

def test_browser_login_email():
    """Browser login by email address"""
    with app.test_client() as client:
        resp = client.post("/auth/login", data={
            "login_id": "chain_star@chain.local", "password": PASSWORD
        }, follow_redirects=False)
        check("Browser login by email redirects (302)", resp.status_code == 302,
              detail=f"status={resp.status_code}")

def test_browser_login_wrong_password():
    """Browser login with wrong password shows error"""
    with app.test_client() as client:
        resp = client.post("/auth/login", data={
            "login_id": "chain_star", "password": "wrong_password_123"
        }, follow_redirects=False)
        check("Browser wrong password returns 200 (not redirect)", resp.status_code == 200,
              detail=f"status={resp.status_code}")

def test_browser_login_all_users():
    """All 5 users can login by username"""
    for username in TEST_USERS:
        with app.test_client() as client:
            resp = client.post("/auth/login", data={
                "login_id": username, "password": PASSWORD
            }, follow_redirects=False)
            check(f"Browser login: {username}", resp.status_code == 302,
                  detail=f"status={resp.status_code}")

def test_browser_login_session():
    """After browser login, session has profile_id"""
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["profile_id"] = None
        resp = client.post("/auth/login", data={
            "login_id": "chain_star", "password": PASSWORD
        }, follow_redirects=False)
        with client.session_transaction() as sess:
            pid = sess.get("profile_id")
            check("Browser login sets session profile_id", pid is not None,
                  detail=f"profile_id={pid}")

# ============================================================
# TASK 9: --verify-login and --force-password flags
# ============================================================
def test_verify_login_flag():
    import subprocess
    result = subprocess.run(
        [sys.executable, "scripts/seed_chain_test_users.py", "--verify-login"],
        capture_output=True, text=True, timeout=120
    )
    check("--verify-login exits 0", result.returncode == 0,
          detail=f"stderr={result.stderr[:200]}" if result.returncode != 0 else None)
    check("--verify-login shows ALL PASS",
          "ALL PASS" in result.stdout,
          detail=f"stdout={result.stdout[-500:]}")

def test_force_password_flag():
    import subprocess
    result = subprocess.run(
        [sys.executable, "scripts/seed_chain_test_users.py", "--force-password"],
        capture_output=True, text=True, timeout=120
    )
    check("--force-password exits 0", result.returncode == 0,
          detail=f"stderr={result.stderr[:200]}" if result.returncode != 0 else None)

# ============================================================
# TASK 10: Session profile_id maps correctly
# ============================================================
def test_session_after_login():
    from services.neon_service import fast_query
    star_rows = fast_query(
        "SELECT id FROM chain_profiles WHERE username = 'chain_star' LIMIT 1",
        default=[]
    )
    expected_pid = star_rows[0]["id"] if star_rows else None
    with app.test_request_context():
        app.config["SECRET_KEY"] = "test_secret"
        from services.auth_service import login_chain_user
        ok, result = login_chain_user("chain_star", PASSWORD)
        check("Login succeeded for session test", ok)
        if ok:
            from flask import session
            check("session has profile_id",
                  session.get("profile_id") is not None,
                  detail=f"profile_id={session.get('profile_id')}")
            if expected_pid:
                check("session profile_id matches chain_profiles.id",
                      session.get("profile_id") == expected_pid,
                      detail=f"session={session.get('profile_id')} expected={expected_pid}")


# ============================================================
# Run all tests
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Phase 56: Seeded Login Verification")
    print("=" * 60)

    tests = [
        ("Seed script exists", test_seed_script_exists),
        ("Run seed idempotently", test_run_seed),
        ("Seed is idempotent", test_seed_idempotent),
        ("All 5 profiles exist", test_profiles_exist),
        ("Login by username (direct call)", test_login_by_username),
        ("Login by email (direct call)", test_login_by_email),
        ("Wrong password fails", test_login_wrong_password),
        ("chain_star has 4 mutual friends", test_friend_follows),
        ("Session profile_id linkage", test_session_after_login),
        ("Friends API after login", test_friends_api_after_login),
        ("Browser login: username", test_browser_login_username),
        ("Browser login: email", test_browser_login_email),
        ("Browser login: wrong password", test_browser_login_wrong_password),
        ("Browser login: all 5 users", test_browser_login_all_users),
        ("Browser login: session profile_id", test_browser_login_session),
        ("--verify-login flag", test_verify_login_flag),
        ("--force-password flag", test_force_password_flag),
    ]

    for name, fn in tests:
        print(f"\n--- {name} ---")
        try:
            fn()
        except Exception as e:
            print(f"  [FAIL] {name} threw: {e}")
            FAIL += 1

    total = PASS + FAIL
    print(f"\n{'=' * 40}")
    print(f"Results: {PASS}/{total} passed, {FAIL} failed")
    print(f"{'=' * 40}")
    sys.exit(0 if FAIL == 0 else 1)
