#!/usr/bin/env python3
"""Investigate the full backend like flow for a real homepage post.

Prints:
1. Homepage payload JSON (feed_items first post)
2. Exact object sent to template
3. id, type, likes_count, comments_count, viewer_has_liked (or is_liked)
4. Authenticated POST /api/home/post/<id>/like with HTTP status + full JSON
5. Neon queries before/after: chain_post_reactions, chain_posts.likes_count
6. Homepage_service returned state after mutation
"""
import json
import os
import re
import sys
import http.client
import urllib.parse
import http.cookiejar
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"
os.environ["CHAIN_DISABLE_DB_PING"] = "1"
os.environ["CHAIN_DISABLE_SCHEMA_CHECK"] = "1"
os.environ["FLASK_ENV"] = "production"
os.environ["ENV"] = "production"

import flask_wtf.csrf
flask_wtf.csrf.generate_csrf = lambda *a, **kw: "test-csrf-token"
flask_wtf.csrf.validate_csrf = lambda *a, **kw: True

from app import create_app
from services.homepage_phase141_service import fetch_posts_v2
from services.neon_service import fast_query

app = create_app()
app.config["WTF_CSRF_ENABLED"] = False

CREDS_PATH = ROOT / "secrets" / "test_credentials.json"

BASE_URL = os.environ.get("NAMVIBE_PUBLIC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")


def load_creds():
    data = json.loads(CREDS_PATH.read_text())
    return data.get("user_a", {})


def extract_csrf_meta(html):
    m = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]*)"', html, re.IGNORECASE)
    return m.group(1) if m else ""


def get_profile_id_by_email(email):
    rows = fast_query(
        "SELECT id FROM chain_profiles WHERE email = %s LIMIT 1",
        [email],
        timeout_ms=10000,
        default=[]
    )
    return rows[0]["id"] if rows else None


def http_request(method, path, data=None, headers=None, cookie_jar=None):
    url = f"{BASE_URL}{path}"
    if headers is None:
        headers = {}
    if data is not None and isinstance(data, str):
        data = data.encode("utf-8")
    if cookie_jar:
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with opener.open(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    else:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body


def print_sep(label):
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")


def main():
    creds = load_creds()
    email = creds.get("email", "alpha@namvibe.com")

    profile_id = get_profile_id_by_email(email)
    if not profile_id:
        print(f"Could not find profile for email {email}")
        return 1

    print(f"Using credentials: email={email} profile_id={profile_id}")

    # Use app test client for template context access
    with app.test_client() as client:
        # --- SET SESSION ---
        print_sep("1. SET SESSION")
        with client.session_transaction() as sess:
            sess["profile_id"] = profile_id
            sess["auth_user_id"] = str(profile_id)
            sess["_user_id"] = str(profile_id)
            sess["user_id"] = str(profile_id)
            sess["age_verified"] = True
            sess["age_check_required"] = False
        print(f"Session set: profile_id={profile_id}")

        # --- FETCH HOMEPAGE ---
        print_sep("2. HOMEPAGE PAYLOAD")
        home_resp = client.get("/?e2e_no_refresh=1")
        print(f"Homepage status: {home_resp.status_code}")

        from flask import template_rendered
        context_data = {}
        def capture_context(sender, template, context, **extra):
            context_data.clear()
            context_data.update(context)
        template_rendered.connect(capture_context, app)

        with app.test_client() as client2:
            with client2.session_transaction() as sess:
                sess["profile_id"] = profile_id
                sess["auth_user_id"] = str(profile_id)
                sess["_user_id"] = str(profile_id)
                sess["user_id"] = str(profile_id)
                sess["age_verified"] = True
                sess["age_check_required"] = False
            client2.get("/?e2e_no_refresh=1")

        template_rendered.disconnect(capture_context, app)

        feed_items = context_data.get("feed_items", [])
        if not feed_items:
            feed_items = (context_data.get("homepage_payload") or {}).get("feed_items", [])
        if not feed_items:
            print("NO FEED ITEMS.")
            return 1

        print(f"Total feed_items: {len(feed_items)}")

        target = None
        for item in feed_items:
            if item.get("type") in ("post", None) and item.get("id"):
                target = item
                break
        if not target:
            print("NO REAL POST FOUND in feed_items")
            return 1

        post_id = target["id"]

        # --- 3. PRINT TARGET FIELDS ---
        print_sep("3. TARGET POST FIELDS")
        print(f"id:               {post_id}")
        print(f"type:             {target.get('type')}")
        print(f"likes_count:      {target.get('likes_count')}")
        print(f"comments_count:   {target.get('comments_count')}")
        print(f"is_liked:         {target.get('is_liked')}")
        print(f"user_liked:       {target.get('user_liked')}")
        print(f"viewer_has_liked: {target.get('viewer_has_liked', '<NOT PRESENT>')}")
        print(f"\nFull target object ({len(target)} fields):")
        print(json.dumps(target, indent=2, default=str))

    # --- 4. QUERY DB BEFORE ---
    print_sep("4. NEON BEFORE LIKE")

    before_reactions = fast_query(
        "SELECT id, profile_id, post_id, reaction_type, created_at FROM chain_post_reactions WHERE post_id = %s AND reaction_type = 'like' ORDER BY created_at",
        [post_id], timeout_ms=10000, default=[]
    )
    before_post = fast_query(
        "SELECT id, likes_count, comments_count FROM chain_posts WHERE id = %s",
        [post_id], timeout_ms=10000, default=[]
    )
    print(f"chain_post_reactions rows before: {len(before_reactions)}")
    for r in before_reactions:
        print(f"  id={r['id']} profile_id={r['profile_id']} type={r['reaction_type']}")
    print(f"chain_posts before: {json.dumps(before_post[0] if before_post else {}, indent=2, default=str)}")

    # --- 5. AUTHENTICATED LIKE VIA DIRECT toggle_like() ---
    print_sep("5. AUTHENTICATED LIKE (direct toggle_like)")

    with app.app_context():
        from services.engagement_service import toggle_like
        from flask import session as flask_session

        # The test_client's session is still active from the template probe above.
        # But toggle_like runs in a fresh context. Use the profile_id we looked up.
        result = toggle_like(str(profile_id), "post", str(post_id))
        liked = bool(result.get("liked"))
        count = int(result.get("count") or 0)

    print(f"Direct toggle_like result: {json.dumps(result, indent=2, default=str)}")

    # --- 6. QUERY DB AFTER LIKE ---
    print_sep("6. NEON AFTER LIKE")

    after_reactions = fast_query(
        "SELECT id, profile_id, post_id, reaction_type, created_at FROM chain_post_reactions WHERE post_id = %s AND reaction_type = 'like' ORDER BY created_at",
        [post_id], timeout_ms=10000, default=[]
    )
    after_post = fast_query(
        "SELECT id, likes_count, comments_count FROM chain_posts WHERE id = %s",
        [post_id], timeout_ms=10000, default=[]
    )
    print(f"chain_post_reactions rows after: {len(after_reactions)}")
    for r in after_reactions:
        owner = " (CURRENT USER)" if r.get("profile_id") == profile_id else ""
        print(f"  id={r['id']} profile_id={r['profile_id']} type={r['reaction_type']}{owner}")
    print(f"chain_posts after: {json.dumps(after_post[0] if after_post else {}, indent=2, default=str)}")

    before_ids = {r["id"] for r in before_reactions}
    after_ids = {r["id"] for r in after_reactions}
    inserted = after_ids - before_ids
    removed = before_ids - after_ids
    print(f"\nReaction rows inserted: {len(inserted)}")
    for rid in inserted:
        print(f"  + {rid}")
    print(f"Reaction rows removed: {len(removed)}")
    for rid in removed:
        print(f"  - {rid}")

    before_likes = (before_post[0] or {}).get("likes_count", 0) or 0
    after_likes = (after_post[0] or {}).get("likes_count", 0) or 0
    print(f"\nchain_posts.likes_count: {before_likes} -> {after_likes} (delta={after_likes - before_likes})")

    # --- 7. TOGGLE BACK (unlike) ---
    print_sep("7. TOGGLE BACK (UNLIKE)")

    with app.app_context():
        result2 = toggle_like(str(profile_id), "post", str(post_id))
        unliked = bool(result2.get("liked"))
        count2 = int(result2.get("count") or 0)

    print(f"Direct toggle_like result: {json.dumps(result2, indent=2, default=str)}")

    # --- 8. QUERY DB AFTER UNLIKE ---
    print_sep("8. NEON AFTER UNLIKE")

    final_reactions = fast_query(
        "SELECT id, profile_id, post_id, reaction_type, created_at FROM chain_post_reactions WHERE post_id = %s AND reaction_type = 'like' ORDER BY created_at",
        [post_id], timeout_ms=10000, default=[]
    )
    final_post = fast_query(
        "SELECT id, likes_count, comments_count FROM chain_posts WHERE id = %s",
        [post_id], timeout_ms=10000, default=[]
    )
    print(f"chain_post_reactions rows final: {len(final_reactions)}")
    for r in final_reactions:
        print(f"  id={r['id']} profile_id={r['profile_id']} type={r['reaction_type']}")
    print(f"chain_posts final: {json.dumps(final_post[0] if final_post else {}, indent=2, default=str)}")

    final_likes = (final_post[0] or {}).get("likes_count", 0) or 0
    back_to_original = (len(final_reactions) == len(before_reactions))
    count_match = (final_likes == before_likes)
    print(f"\nBack to original reaction count ({len(before_reactions)} == {len(final_reactions)}): {back_to_original}")
    print(f"Back to original likes_count ({before_likes} == {final_likes}): {count_match}")

    # --- 9. VERIFY HOMEPAGE_SERVICE POST-MUTATION ---
    print_sep("9. HOMEPAGE_SERVICE POST-MUTATION STATE")

    with app.app_context():
        posts_after, cached, err = fetch_posts_v2(
            ["id", "profile_id", "caption", "content", "body", "thumbnail_url", "media_url", "video_url", "mime_type", "post_type", "likes_count", "comments_count", "views_count", "shares_count", "created_at"],
            timeout_ms=20000, limit=20, viewer_id=profile_id,
        )
        print(f"fetch_posts_v2 returned {len(posts_after)} posts (cached={cached}, err={err})")

        our_post = None
        for p in posts_after:
            if p.get("id") == post_id:
                our_post = p
                break

        if our_post:
            print(f"\nOur post after mutations (like then unlike):")
            print(f"  id:               {our_post.get('id')}")
            print(f"  type:             {our_post.get('type')}")
            print(f"  likes_count:      {our_post.get('likes_count')}")
            print(f"  comments_count:   {our_post.get('comments_count')}")
            print(f"  is_liked:         {our_post.get('is_liked')}")
            print(f"  user_liked:       {our_post.get('user_liked')}")
            print(f"  viewer_has_liked: {our_post.get('viewer_has_liked', '<NOT PRESENT>')}")
            print(f"\nFull normalized object:")
            print(json.dumps(our_post, indent=2, default=str))
        else:
            print(f"\nOur post ({post_id}) NOT found in fresh fetch_posts_v2 results")

    # --- SUMMARY ---
    print_sep("SUMMARY")
    print(f"Post ID:         {post_id}")
    print(f"viewer_has_liked: {'PRESENT' if target.get('viewer_has_liked') is not None else 'MISSING from normalize_post_v2 (uses is_liked/user_liked instead)'}")
    print(f"")
    print(f"LIKE TOGGLE:")
    print(f"  Direct toggle_like: {json.dumps(result, default=str)}")
    print(f"  DB: chain_post_reactions  {len(before_reactions)} -> {len(after_reactions)}  (inserted={len(inserted)}, removed={len(removed)})")
    print(f"  DB: chain_posts.likes_count  {before_likes} -> {after_likes}")
    print(f"")
    print(f"UNLIKE TOGGLE:")
    print(f"  Direct toggle_like: {json.dumps(result2, default=str)}")
    print(f"  DB: chain_post_reactions  {len(after_reactions)} -> {len(final_reactions)}")
    print(f"  DB: chain_posts.likes_count  {after_likes} -> {final_likes}")
    print(f"")
    print(f"VERDICT:")
    print(f"  Reaction row lifecycle: {'PASS' if len(inserted) == 1 else 'FAIL'} (expected 1 insert)")
    print(f"  Count updated:          {'PASS' if after_likes == before_likes + 1 else 'FAIL'} (expected +1)")
    print(f"  Unlike removes row:     {'PASS' if len(removed) == 1 else 'FAIL'} (expected 1 delete)")
    print(f"  Count reverted:         {'PASS' if final_likes == before_likes else 'FAIL'} (expected {before_likes})")
    print(f"  Homepage is_liked:      {'PASS' if our_post and our_post.get('is_liked') == False else 'FAIL'} (expected False after unlike)")
    print(f"  viewer_has_liked field: {'PASS' if 'viewer_has_liked' in (our_post or {}) else 'NOT SET in normalize_post_v2'}")

    print(f"\nSOURCE OF viewer_has_liked MISSING:")
    print(f"  File: services/homepage_phase141_service.py")
    print(f"  Function: normalize_post_v2() at line 188")
    print(f"  Lines 209-240: returns is_liked (line 236) and user_liked (line 237)")
    print(f"  but does NOT include 'viewer_has_liked' in the return dict.")

    # --- 10. HTTP ENDPOINT TEST (real gunicorn) ---
    print_sep("10. HTTP ENDPOINT TEST (authenticated like via real gunicorn)")
    import requests as http_requests
    BASE = os.environ.get("NAMVIBE_PUBLIC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
    LikeResponse = type("LikeResponse", (), {"status": 0, "json": lambda self: {}})()

    try:
        s = http_requests.Session()
        # Login via HTTP
        r = s.get(f"{BASE}/auth/login", timeout=15)
        csrf_html = re.search(r'<meta[^>]*name=["\']csrf-token["\'][^>]*content=["\']([^"\']+)["\']', r.text)
        csrf_token = csrf_html.group(1) if csrf_html else ""
        r = s.post(f"{BASE}/auth/login", data={
            "login_id": "alpha@namvibe.com",
            "password": "TestPassword123!",
            "csrf_token": csrf_token,
        }, allow_redirects=False, timeout=15)
        if r.status_code in (302, 303, 307) and r.headers.get("Location"):
            s.get(BASE + r.headers["Location"], timeout=15)

        # Get homepage for API CSRF token
        r = s.get(f"{BASE}/", timeout=30)
        csrf_html = re.search(r'<meta[^>]*name=["\']csrf-token["\'][^>]*content=["\']([^"\']+)["\']', r.text)
        csrf_token = csrf_html.group(1) if csrf_html else ""

        # Like via HTTP
        headers = {"X-CSRFToken": csrf_token, "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"}
        like_url = f"{BASE}/api/home/post/{post_id}/like"
        r_like = s.post(like_url, json={"post_id": post_id}, headers=headers, timeout=15)
        LikeResponse.status = r_like.status_code
        LikeResponse.json = lambda self: r_like.json()
        print(f"  HTTP LIKE {like_url}")
        print(f"  Status: {r_like.status_code}")
        print(f"  Body: {json.dumps(r_like.json(), indent=4, default=str)}")

        # Toggle back
        r_unlike = s.post(like_url, json={"post_id": post_id}, headers=headers, timeout=15)
        print(f"  HTTP UNLIKE {like_url}")
        print(f"  Status: {r_unlike.status_code}")
        print(f"  Body: {json.dumps(r_unlike.json(), indent=4, default=str)}")
    except Exception as e:
        print(f"  HTTP endpoint test SKIPPED or FAILED: {e}")
        LikeResponse.status = -1
        LikeResponse.json = lambda self: {}

    return 0


if __name__ == "__main__":
    sys.exit(main())
