#!/usr/bin/env python3
"""Quick check: latest promo reels should appear in homepage and reels feeds for a seeded viewer."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ.setdefault("ALLOW_LOCAL_AUTH_FALLBACK", "true")
os.environ.setdefault("WTF_CSRF_ENABLED", "0")

from app import app as flask_app
from services.neon_service import fast_query

flask_app.config["WTF_CSRF_ENABLED"] = False

CREDS = json.loads((ROOT / "secrets" / "test_credentials.json").read_text())


def identity(username):
    row = CREDS.get(username) or {}
    return {
        "username": row.get("username") or username,
        "profile_id": row.get("profile_id"),
        "auth_user_id": row.get("auth_user_id"),
        "email": row.get("email"),
        "full_name": row.get("full_name") or username,
    }


def login(client, ident):
    with client.session_transaction() as sess:
        sess["auth_user_id"] = ident["auth_user_id"]
        sess["profile_id"] = ident["profile_id"]
        sess["user_id"] = ident["profile_id"]
        sess["username"] = ident["username"]
        sess["full_name"] = ident["full_name"]
        sess["auth_email"] = ident["email"]
        sess["email"] = ident["email"]
        sess["logged_in"] = True
        sess["profile_completed"] = True


def main():
    uploader = identity("chain_star")
    viewer = identity("chain_moon")
    rows = fast_query(
        """
        SELECT id, caption, created_at
        FROM chain_reels
        WHERE profile_id = %s AND caption LIKE %s AND deleted_at IS NULL
        ORDER BY created_at DESC
        LIMIT 5
        """,
        (uploader["profile_id"], "PROMO_MULTI_%"),
        timeout_ms=8000,
        default=[],
    )
    reel_ids = [str(row.get("id")) for row in rows]
    if not reel_ids:
        print("FAIL no promo reels found")
        return 1

    client = flask_app.test_client()
    login(client, viewer)

    reels_feed = client.get("/reels/api/reels/feed?limit=20")
    reels_payload = reels_feed.get_json(silent=True) or {}
    reels_seen = {str(item.get("id")) for item in reels_payload.get("reels", [])}

    homepage_feed = client.get("/api/homepage/feed?limit=20")
    homepage_payload = homepage_feed.get_json(silent=True) or {}
    homepage_reels = (((homepage_payload or {}).get("payload") or {}).get("reels")) or []
    homepage_seen = {str(item.get("id")) for item in homepage_reels}

    print(f"promo_reels={len(reel_ids)} reels_feed_visible={len(reel_ids and [rid for rid in reel_ids if rid in reels_seen])} homepage_visible={len(reel_ids and [rid for rid in reel_ids if rid in homepage_seen])}")
    print(f"homepage_status={homepage_feed.status_code} reels_status={reels_feed.status_code}")
    return 0 if any(rid in homepage_seen for rid in reel_ids) else 1


if __name__ == "__main__":
    raise SystemExit(main())
