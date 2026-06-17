"""
Phase 77 real registration debug.

Run:
  python3 scripts/debug_phase77_real_register.py
"""

import os
import re
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("ENV", "development")
os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
os.environ.setdefault("SECRET_KEY", "test-phase77-debug-secret-key")

from app import create_app
from services.neon_service import fast_query


def extract_csrf(html):
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return match.group(1) if match else None


def main():
    app = create_app()
    client = app.test_client()
    suffix = uuid.uuid4().hex[:8]
    email = f"phase77real{suffix}@namvibe.com"
    username = f"phase77real{suffix[:6]}"
    password = "Phase77RealPass!"

    print("Phase 77 real register debug")
    print("[1] GET /auth/register")
    get_resp = client.get("/auth/register")
    print("status:", get_resp.status_code)
    print("Set-Cookie:")
    for cookie in get_resp.headers.getlist("Set-Cookie"):
        print(cookie)

    csrf = extract_csrf(get_resp.data.decode("utf-8"))
    print("csrf extracted:", bool(csrf))
    if not csrf:
        return 1

    payload = {
        "csrf_token": csrf,
        "full_name": "Phase77 Real User",
        "email": email,
        "username": username,
        "phone": f"+26481{suffix[:6]}",
        "country_origin": "Namibia",
        "date_of_birth": "2000-01-15",
        "gender": "female",
        "password": password,
        "confirm_password": password,
        "terms": "on",
    }

    print("[2] POST /auth/register unique user")
    post_resp = client.post("/auth/register", data=payload, follow_redirects=False)
    print("status:", post_resp.status_code)
    print("redirect location:", post_resp.headers.get("Location"))
    body = post_resp.data.decode("utf-8", errors="replace")
    if post_resp.status_code == 200:
        alert = re.search(r'chain-auth-alert[^>]*>\s*(.*?)\s*</div>', body, re.S)
        print("page error:", re.sub(r"\s+", " ", alert.group(1)).strip() if alert else "")

    print("[3] DB profile lookup")
    try:
        rows = fast_query(
            """
            SELECT id, auth_user_id, email, username, date_of_birth, country_origin, created_at
            FROM chain_profiles
            WHERE lower(email) = lower(%s) OR lower(username) = lower(%s)
            LIMIT 1
            """,
            (email, username),
            timeout_ms=2500,
            default=[],
        )
        print("profile found:", bool(rows))
        if rows:
            row = rows[0]
            print("profile:", {
                "id": row.get("id"),
                "auth_user_id": row.get("auth_user_id"),
                "email": row.get("email"),
                "username": row.get("username"),
                "date_of_birth": row.get("date_of_birth"),
                "country_origin": row.get("country_origin"),
            })
    except Exception as error:
        print("profile lookup error:", error)

    print("[4] Login attempt for posted user")
    login_client = app.test_client()
    login_get = login_client.get("/auth/login")
    login_csrf = extract_csrf(login_get.data.decode("utf-8"))
    login_resp = login_client.post(
        "/auth/login",
        data={"csrf_token": login_csrf, "login_id": email, "password": password},
        follow_redirects=False,
    )
    print("login status:", login_resp.status_code)
    print("login redirect location:", login_resp.headers.get("Location"))
    if login_resp.status_code == 200:
        login_body = login_resp.data.decode("utf-8", errors="replace")
        alert = re.search(r'chain-auth-alert[^>]*>\s*(.*?)\s*</div>', login_body, re.S)
        print("login page error:", re.sub(r"\s+", " ", alert.group(1)).strip() if alert else "")

    return 0


if __name__ == "__main__":
    sys.exit(main())
