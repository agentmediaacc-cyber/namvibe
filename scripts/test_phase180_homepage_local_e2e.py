#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ.setdefault("FLASK_TESTING", "1")

from app import app


CREDS_PATH = ROOT / "secrets" / "test_credentials.json"


class Results:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def ok(self, msg):
        self.passed += 1
        print(f"PASS  {msg}")

    def fail(self, msg):
        self.failed += 1
        print(f"FAIL  {msg}")


def load_identities():
    data = json.loads(CREDS_PATH.read_text())
    user_a = data.get("user_a") or {}
    user_b = data.get("user_b") or {}
    if not user_a.get("profile_id") or not user_a.get("auth_user_id"):
        raise SystemExit("user_a missing profile_id/auth_user_id in secrets/test_credentials.json")
    if not user_b.get("profile_id") or not user_b.get("auth_user_id"):
        raise SystemExit("user_b missing profile_id/auth_user_id in secrets/test_credentials.json")
    user_a["canonical_username"] = user_a.get("canonical_username") or user_a.get("username") or "alpha"
    user_b["canonical_username"] = user_b.get("canonical_username") or user_b.get("username") or "beta"
    return user_a, user_b


def login_client(client, identity):
    with client.session_transaction() as sess:
        sess["auth_user_id"] = identity["auth_user_id"]
        sess["user_id"] = identity["auth_user_id"]
        sess["profile_id"] = identity["profile_id"]
        sess["username"] = identity["canonical_username"]
        sess["auth_email"] = identity.get("email")
        sess["email"] = identity.get("email")
        sess["full_name"] = identity.get("full_name") or identity["canonical_username"]
        sess["logged_in"] = True
        sess["profile_completed"] = True


def main():
    results = Results()
    alpha, beta = load_identities()

    client = app.test_client()
    login_client(client, alpha)

    homepage = client.get("/", follow_redirects=True)
    html = homepage.get_data(as_text=True)
    if homepage.status_code == 200:
        results.ok("homepage returns 200 for authenticated local user")
    else:
        results.fail(f"homepage returned {homepage.status_code}")
        print(f"\nSUMMARY: {results.passed} passed, {results.failed} failed")
        raise SystemExit(1)

    for token in (
        'data-action="open-menu"',
        'data-action="open-create"',
        'data-action="open-notifications"',
        'data-action="post-more"',
        'data-action="send-drawer-comment"',
        '/static/js/namvibe_home_premium_v2.js',
        '/static/css/namvibe_home_premium_v2.css',
        'nv-video-overlay',
    ):
        if token in html:
            results.ok(f"homepage includes {token}")
        else:
            results.fail(f"homepage missing {token}")

    for path in ("/discover/", "/notifications/", "/messages/", "/profile/", "/live/", "/live/studio"):
        resp = client.get(path, follow_redirects=False)
        if resp.status_code in (200, 302):
            results.ok(f"{path} reachable ({resp.status_code})")
        else:
            results.fail(f"{path} returned {resp.status_code}")

    profile_alias = f"/profile/@{beta['canonical_username']}"
    alias_resp = client.get(profile_alias, follow_redirects=False)
    if alias_resp.status_code in (200, 302, 404):
        results.ok(f"{profile_alias} responded ({alias_resp.status_code})")
    else:
        results.fail(f"{profile_alias} returned {alias_resp.status_code}")

    no_placeholders = all(bad not in html for bad in ('href="#"', 'javascript:void(0)', 'javascript:;'))
    if no_placeholders:
        results.ok("homepage renders without placeholder hrefs")
    else:
        results.fail("homepage still renders placeholder hrefs")

    has_real_ids = bool(re.search(r'data-action="(?:like|comment|share|save)"[^>]*data-id="[^"]+"', html))
    if has_real_ids:
        results.ok("homepage feed actions render real ids")
    else:
        results.fail("homepage feed actions missing real ids")

    print(f"\nSUMMARY: {results.passed} passed, {results.failed} failed")
    raise SystemExit(1 if results.failed else 0)


if __name__ == "__main__":
    main()
