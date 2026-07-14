#!/usr/bin/env python3
"""Test profile routes: own profile, edit, public profile, homepage links, data exposure."""

import json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PASS = 0
FAIL = 0
WARN = 0

APP = None
CLIENT = None
PROFILE_ID = None
AUTH_USER_ID = None


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name} {detail}")
        FAIL += 1


def warn(name, detail=""):
    global WARN
    print(f"  WARN {name} {detail}")
    WARN += 1


def _setup_app():
    global APP, CLIENT
    os.environ["CHAIN_FAST_LOCAL"] = "1"
    os.environ["WTF_CSRF_ENABLED"] = "False"
    from app import app as flask_app
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["SECRET_KEY"] = "test-secret-key"
    APP = flask_app
    CLIENT = flask_app.test_client()


def _login_client(profile_id, auth_user_id=None):
    with CLIENT.session_transaction() as sess:
        sess["profile_id"] = profile_id
        sess["auth_user_id"] = auth_user_id or profile_id
        sess["user_id"] = auth_user_id or profile_id
        sess["age_verified"] = True
        sess["age_check_required"] = False
        sess["username"] = "alpha_user"


def _get_public_profile_ids():
    from services.neon_service import fast_query
    results = fast_query(
        "SELECT id, username FROM chain_profiles WHERE deleted_at IS NULL AND username IS NOT NULL ORDER BY created_at DESC LIMIT 5",
        timeout_ms=5000,
        default=[]
    )
    return [(r["id"], r["username"]) for r in results] if results else []


def _get_alpha_profile():
    from services.neon_service import fast_query
    results = fast_query(
        "SELECT id, auth_user_id, username, email FROM chain_profiles WHERE email = 'alpha@namvibe.com' LIMIT 1",
        timeout_ms=5000,
        default=[]
    )
    return results[0] if results else None


def test_template_compiles():
    print("\n--- Template compilation ---")
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(ROOT / "templates")))
    for name in ["profile/index.html", "profile/public.html", "profile/edit.html",
                  "profile/base_profile.html", "profile/not_found.html",
                  "profile/private_profile.html"]:
        try:
            env.get_template(name)
            check(f"{name} template compiles", True)
        except Exception as e:
            check(f"{name} template compiles", False, str(e))


def test_own_profile_redirects_when_logged_out():
    print("\n--- /profile/ requires login ---")
    resp = CLIENT.get("/profile/", follow_redirects=False)
    check("/profile/ redirects to login when logged out",
          resp.status_code in (302, 303) and "/auth/login" in (resp.headers.get("Location") or ""),
          f"Got {resp.status_code} Location={resp.headers.get('Location')}")


def test_own_profile_opens_when_logged_in():
    print("\n--- /profile/ opens when logged in ---")
    _login_client(PROFILE_ID, AUTH_USER_ID)
    resp = CLIENT.get("/profile/")
    check("/profile/ returns 200", resp.status_code == 200, str(resp.status_code))
    check("/profile/ body has profile content", b"profile" in resp.data.lower() or b"Profile" in resp.data)
    if resp.status_code == 200:
        has_edit = b"/profile/edit" in resp.data or b"Edit Profile" in resp.data
        check("/profile/ has edit link", has_edit)
        has_avatar = b"nv-avatar" in resp.data or b"avatar" in resp.data
        check("/profile/ has avatar markup", has_avatar)
        has_display_name = b"display_name" in resp.data or b"nv-display-name" in resp.data
        check("/profile/ has display name", has_display_name)


def test_profile_edit_requires_login():
    print("\n--- /profile/edit requires login ---")
    CLIENT = APP.test_client()
    resp = CLIENT.get("/profile/edit", follow_redirects=False)
    check("/profile/edit redirects to login when logged out",
          resp.status_code in (302, 303) and "/auth/login" in (resp.headers.get("Location") or ""),
          f"Got {resp.status_code}")


def test_profile_edit_opens_when_logged_in():
    print("\n--- /profile/edit opens when logged in ---")
    _login_client(PROFILE_ID, AUTH_USER_ID)
    resp = CLIENT.get("/profile/edit")
    check("/profile/edit returns 200", resp.status_code == 200, str(resp.status_code))
    if resp.status_code == 200:
        has_form = b"<form" in resp.data or b"method=\"POST\"" in resp.data
        check("/profile/edit has form", has_form)
        has_fields = any(f in resp.data for f in [b"name=\"full_name\"", b"name=\"username\"", b"name=\"bio\""])
        check("/profile/edit has profile fields", has_fields)
        has_avatar_upload = b"name=\"avatar\"" in resp.data or b"avatar" in resp.data
        check("/profile/edit has avatar upload", has_avatar_upload)


def test_profile_edit_post_updates_profile():
    print("\n--- /profile/edit POST updates profile ---")
    _login_client(PROFILE_ID, AUTH_USER_ID)

    resp = CLIENT.post("/profile/edit", data={
        "full_name": "Test Alpha User",
        "username": "alpha_user",
        "bio": "Updated via test",
        "location": "Test City",
    }, follow_redirects=False)

    check("/profile/edit POST returns redirect",
          resp.status_code in (302, 303),
          f"Got {resp.status_code}")

    resp2 = CLIENT.get("/profile/")
    bio_in_page = b"Updated via test" in resp2.data
    check("/profile/ shows updated bio", bio_in_page)


def test_public_profile_by_username():
    print("\n--- /profile/<username> public profile ---")
    CLIENT = APP.test_client()
    profiles = _get_public_profile_ids()
    if not profiles:
        warn("No public profiles found in DB")
        return

    pid, uname = profiles[0]
    resp = CLIENT.get(f"/profile/{uname}", follow_redirects=True)
    check(f"/profile/{uname} returns 200/404",
          resp.status_code in (200, 404),
          f"Got {resp.status_code}")
    if resp.status_code == 200:
        check(f"/profile/{uname} body has content", len(resp.data) > 500)


def test_public_profile_shell():
    print("\n--- /profile/<username>?shell=1 public shell ---")
    CLIENT = APP.test_client()
    profiles = _get_public_profile_ids()
    if not profiles:
        warn("No public profiles found for shell test")
        return

    pid, uname = profiles[0]
    resp = CLIENT.get(f"/profile/{uname}?shell=1", follow_redirects=True)
    check(f"/profile/{uname}?shell=1 returns 200",
          resp.status_code == 200,
          f"Got {resp.status_code}")


def test_public_profile_no_email_phone():
    print("\n--- Public profile does not expose email/phone/wallet ---")
    CLIENT = APP.test_client()
    profiles = _get_public_profile_ids()
    if not profiles:
        warn("No public profiles for exposure test")
        return

    for pid, uname in profiles:
        resp = CLIENT.get(f"/profile/{uname}", follow_redirects=True)
        if resp.status_code != 200:
            continue
        body = resp.data.decode("utf-8", errors="replace")
        body_lower = body.lower()
        check(f"Public profile {uname} has no email field in HTML",
              "email" not in body_lower.replace("email_verified", "").replace("@", "&#64;") or
              "type=\"email\"" not in body)
        check(f"Public profile {uname} has no phone field in HTML",
              re.search(r'name\s*=\s*"phone"', body) is None and re.search(r'>\s*\+?\d{7,}\s*<', body) is None)
        check(f"Public profile {uname} has no wallet_balance in HTML",
              "wallet_balance" not in body_lower)


def test_public_profile_has_public_content():
    print("\n--- Public profile has public content ---")
    CLIENT = APP.test_client()
    profiles = _get_public_profile_ids()
    if not profiles:
        warn("No public profiles for content test")
        return

    for pid, uname in profiles:
        resp = CLIENT.get(f"/profile/{uname}?shell=1", follow_redirects=True)
        if resp.status_code != 200:
            continue
        body = resp.data.decode("utf-8", errors="replace")
        check(f"Public profile {uname} has posts section", "posts" in body.lower() or "Posts" in body)
        check(f"Public profile {uname} has tabs", "tab" in body.lower())


def test_homepage_contains_profile_links():
    print("\n--- Homepage contains profile links ---")
    CLIENT = APP.test_client()
    from services.homepage_phase141_service import fetch_posts_v2
    with APP.app_context():
        posts, cached, err = fetch_posts_v2(
            ["id", "profile_id", "caption", "content", "body", "thumbnail_url", "media_url", "video_url",
             "mime_type", "post_type", "likes_count", "comments_count", "views_count", "shares_count", "created_at"],
            timeout_ms=20000, limit=10, viewer_id=PROFILE_ID,
        )
    if not posts:
        warn("No posts returned from fetch_posts_v2")
        return

    first_post = posts[0]
    has_profile_url = "profile_url" in first_post
    check("Post JSON has profile_url field", has_profile_url)
    if has_profile_url:
        url = first_post["profile_url"]
        check(f"profile_url is /profile/@ format", url.startswith("/profile/"), f"Got {url}")


def test_public_profile_by_profile_id():
    print("\n--- /profile/id/<profile_id> public profile ---")
    CLIENT = APP.test_client()
    profiles = _get_public_profile_ids()
    if not profiles:
        warn("No public profiles for ID route test")
        return

    pid, uname = profiles[0]
    resp = CLIENT.get(f"/profile/id/{pid}", follow_redirects=True)
    check(f"/profile/id/{pid} returns 200/404",
          resp.status_code in (200, 404),
          f"Got {resp.status_code}")


def test_not_found_returns_404():
    print("\n--- /profile/<nonexistent> returns 404 ---")
    CLIENT = APP.test_client()
    resp = CLIENT.get("/profile/thisuserdoesnotexist999999", follow_redirects=True)
    check("Nonexistent profile returns 404", resp.status_code == 404, f"Got {resp.status_code}")


def test_profile_no_slash_redirect():
    print("\n--- /profile (no slash) redirects to /profile/ ---")
    CLIENT = APP.test_client()
    _login_client(PROFILE_ID, AUTH_USER_ID)
    resp = CLIENT.get("/profile", follow_redirects=False)
    check("/profile (no slash) returns 302 or 200",
          resp.status_code in (200, 302),
          f"Got {resp.status_code}")


def test_viewer_has_liked_field():
    print("\n--- viewer_has_liked field in normalize_post_v2 ---")
    from services.homepage_phase141_service import normalize_post_v2 as normalize
    row = {
        "id": "test-id",
        "profile_id": PROFILE_ID,
        "likes_count": 1,
        "comments_count": 0,
    }
    profile_map = {
        PROFILE_ID: {
            "id": PROFILE_ID,
            "username": "alpha_user",
        }
    }
    try:
        result = normalize(row, profile_map)
        has = "viewer_has_liked" in result
        check("normalize_post_v2 includes viewer_has_liked", has)
        if has:
            check("viewer_has_liked is boolean", isinstance(result["viewer_has_liked"], bool))
    except Exception as e:
        check("normalize_post_v2 runs without error", False, str(e))


def run():
    global PROFILE_ID, AUTH_USER_ID

    print("=" * 60)
    print("PROFILE ROUTES TEST")
    print("=" * 60)

    _setup_app()

    alpha = _get_alpha_profile()
    if not alpha:
        print("\n  WARN  Could not find alpha@namvibe.com profile. Using fallback.")
        with APP.app_context():
            from services.neon_service import fast_query
            fallback = fast_query(
                "SELECT id, auth_user_id, username FROM chain_profiles WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT 1",
                timeout_ms=5000, default=[]
            )
            if fallback:
                PROFILE_ID = fallback[0]["id"]
                AUTH_USER_ID = fallback[0].get("auth_user_id") or PROFILE_ID
            else:
                print("  FAIL  No profiles found in database")
                return False
    else:
        PROFILE_ID = alpha["id"]
        AUTH_USER_ID = alpha.get("auth_user_id") or PROFILE_ID

    test_template_compiles()

    with APP.app_context():
        test_own_profile_redirects_when_logged_out()
        test_own_profile_opens_when_logged_in()
        test_profile_edit_requires_login()
        test_profile_edit_opens_when_logged_in()
        test_profile_edit_post_updates_profile()
        test_public_profile_by_username()
        test_public_profile_shell()
        test_public_profile_no_email_phone()
        test_public_profile_has_public_content()
        test_homepage_contains_profile_links()
        test_public_profile_by_profile_id()
        test_not_found_returns_404()
        test_profile_no_slash_redirect()
        test_viewer_has_liked_field()

    print(f"\n{'=' * 60}")
    total = PASS + FAIL + WARN
    print(f"PASS: {PASS}/{total}  FAIL: {FAIL}  WARN: {WARN}")
    if FAIL == 0:
        print("RESULT: PASS")
    else:
        print("RESULT: FAIL")
    print(f"{'=' * 60}")
    return FAIL == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
