#!/usr/bin/env python3
"""
End-to-end audit of the Like/Comment pipeline for a real logged-in homepage post.

Target user: alpha_user / TestPassword123!
Target server: http://127.0.0.1:8080

Usage:
  NAMVIBE_PUBLIC_BASE_URL=http://127.0.0.1:8080 ./venv/bin/python scripts/audit_real_like_pipeline.py
"""

import asyncio
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["WTF_CSRF_ENABLED"] = "False"

ALPHA_EMAIL = "alpha@namvibe.com"
ALPHA_PASSWORD = "TestPassword123!"
BASE_URL = "http://127.0.0.1:8080"
SCREENSHOT_DIR = Path("/tmp")

RESULTS = {}

def log(msg):
    print(f"[audit] {msg}", flush=True)


# ── Lazy DB init ─────────────────────────────────────────────────
_flask_app = None
_fast_query = None
_write_query = None

def _init_db():
    global _flask_app, _fast_query, _write_query
    if _flask_app is not None:
        return _flask_app
    from app import app as _flask_app
    _flask_app.config["TESTING"] = True
    _flask_app.config["WTF_CSRF_ENABLED"] = False
    from services.neon_service import fast_query as _fast_query, write_query as _write_query
    return _flask_app

def db_query(sql, params=None, timeout_ms=15000):
    app = _init_db()
    with app.app_context():
        try:
            return _fast_query(sql, params or [], timeout_ms=timeout_ms, default=[])
        except Exception as e:
            log(f"  DB query error: {e}")
            return []

def db_write(sql, params=None):
    app = _init_db()
    with app.app_context():
        try:
            return _write_query(sql, params or [])
        except Exception as e:
            log(f"  DB write error: {e}")
            return None


async def audit():
    from playwright.async_api import async_playwright
    import requests

    all_console = []
    network_reqs = []    # ALL requests
    network_resps = {}   # url -> response info
    failed_reqs = []
    profile_id = None
    auth_user_id = None

    db_before = {}
    db_after_first = {}
    db_after_second = {}
    http_first = {}
    http_second = {}
    ui_after_first = {}
    ui_after_refresh1 = {}
    ui_after_second = {}
    ui_after_refresh2 = {}
    selected_post = {}

    # ── Pre-fetch profile ────────────────────────────────────────
    rows = db_query(
        "SELECT id, auth_user_id, username FROM chain_profiles WHERE email = %s LIMIT 1",
        [ALPHA_EMAIL],
    )
    if rows:
        profile_id = str(rows[0]["id"])
        auth_user_id = str(rows[0].get("auth_user_id") or rows[0]["id"])
        log(f"Alpha profile_id: {profile_id}")
        RESULTS["user_info"] = {"profile_id": profile_id, "auth_user_id": auth_user_id, "email": ALPHA_EMAIL}

    # ── Cache snapshot ───────────────────────────────────────────
    from engines.cache_engine import _CACHE as cache_store
    cache_before = {}
    for k in list(cache_store.keys()):
        if "homepage" in k.lower() or "feed" in k.lower() or "like" in k.lower():
            cache_before[k] = str(type(cache_store[k]))
    RESULTS["cache_before"] = cache_before

    # ── Login via requests + cookie injection ────────────────────
    log("Logging in via requests session...")
    sess = requests.Session()
    login_resp = sess.get(f"{BASE_URL}/auth/login")
    csrf_match = re.search(r'name=["\']csrf_token["\'].*?value=["\']([^"\']+)', login_resp.text)
    apk_match = re.search(r'name=["\']apk_csrf_token["\'].*?value=["\']([^"\']+)', login_resp.text)
    csrf_val = csrf_match.group(1) if csrf_match else ""
    apk_val = apk_match.group(1) if apk_match else ""
    log(f"  CSRF token: {csrf_val[:20]}...")

    login_post = sess.post(f"{BASE_URL}/auth/login", data={
        "login_id": ALPHA_EMAIL,
        "password": ALPHA_PASSWORD,
        "csrf_token": csrf_val,
        "apk_csrf_token": apk_val,
    }, allow_redirects=True)
    log(f"  Login POST: status={login_post.status_code} url={login_post.url}")
    logged_in = "login" not in login_post.url.lower() or login_post.status_code == 302
    log(f"  Logged in: {logged_in}")

    # Verify session works
    home_resp = sess.get(f"{BASE_URL}/?e2e_no_refresh=1")
    log(f"  Homepage load: {home_resp.status_code} ({len(home_resp.text)} bytes)")
    if "login" in home_resp.url:
        log("  WARNING: Redirected to login. Login may have failed.")

    # Check likes-state API directly via the session
    likes_state_resp = sess.get(
        f"{BASE_URL}/api/home/likes-state?type=post&ids=test-id-1,test-id-2",
    )
    log(f"  Likes-state API: {likes_state_resp.status_code}")
    try:
        ls_data = likes_state_resp.json()
        log(f"  Likes-state response: {json.dumps(ls_data, default=str)[:200]}")
        RESULTS["likes_state_api_direct"] = ls_data
    except:
        log(f"  Likes-state body: {likes_state_resp.text[:200]}")
        RESULTS["likes_state_api_direct"] = {"error": likes_state_resp.text[:200]}

    # ── Launch browser ───────────────────────────────────────────
    log("\nStarting Playwright...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 1024},
            ignore_https_errors=True,
        )

        # Inject session cookies
        for cookie in sess.cookies:
            try:
                await context.add_cookies([{
                    "name": cookie.name,
                    "value": cookie.value,
                    "domain": "127.0.0.1",
                    "path": cookie.path or "/",
                }])
            except Exception as e:
                log(f"  Cookie error: {e}")
        log(f"  Cookies injected: {[c.name for c in sess.cookies]}")

        # Network interception
        async def on_req(request):
            network_reqs.append({
                "url": request.url, "method": request.method,
                "headers": dict(request.headers),
                "timestamp": time.time(),
            })

        async def on_resp(response):
            url = response.url
            resp_info = {"status": response.status, "url": url}
            if "like" in url.lower() and response.request.method == "POST":
                try:
                    resp_info["body"] = await response.json()
                except:
                    try:
                        resp_info["body"] = await response.text()
                    except:
                        resp_info["body"] = "<unreadable>"
            network_resps[url] = resp_info

        async def on_req_failed(request):
            failed_reqs.append({
                "url": request.url, "method": request.method,
                "failure": str(request.failure),
            })

        context.on("request", on_req)
        context.on("response", on_resp)
        context.on("requestfailed", on_req_failed)

        page = await context.new_page()

        page.on("console", lambda msg: all_console.append({
            "type": msg.type, "text": msg.text, "time": time.time(),
        }))
        page.on("pageerror", lambda err: all_console.append({
            "type": "page_error", "text": str(err), "time": time.time(),
        }))

        # ── Navigate to homepage ──────────────────────────────────
        log("Loading homepage...")
        await page.goto(f"{BASE_URL}/?e2e_no_refresh=1", wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)

        await page.screenshot(path=str(SCREENSHOT_DIR / "namvibe_like_before.png"), full_page=True)
        log("Screenshot saved: /tmp/namvibe_like_before.png")

        # ── Wait for hydration ────────────────────────────────────
        log("Waiting for hydration signals...")
        for signal in ["NAMVIBE_HOME_INTERACTIONS_READY", "NAMVIBE_HOME_LIKES_READY"]:
            try:
                val = await page.wait_for_function(
                    f"typeof window.{signal} !== 'undefined'", timeout=15000,
                )
                ready = await page.evaluate(f"window.{signal}")
                log(f"  {signal} = {ready}")
            except Exception as e:
                log(f"  {signal} not found: {e}")

        await page.wait_for_timeout(2000)

        # Also query all hydrateVisibleLikeStates responses
        likes_state_calls = [r for r in network_resps.values()
                            if "likes-state" in r.get("url", "")]
        for ls in likes_state_calls:
            log(f"  Likes-state call: {ls.get('status')} - {ls.get('url')[:100]}")
            if "body" in ls:
                log(f"    body: {json.dumps(ls['body'], default=str)[:200]}")
        RESULTS["likes_state_calls"] = likes_state_calls

        # ── Find post cards ───────────────────────────────────────
        log("\nScanning homepage cards...")
        card_info = await page.evaluate("""
            () => {
                const cards = document.querySelectorAll('.nv-post, article[data-type], [data-post-id], [data-id]');
                const results = [];
                cards.forEach(card => {
                    const type = card.dataset.type || 'unknown';
                    const postId = card.dataset.postId || '';
                    const id = card.dataset.id || card.dataset.itemId || '';
                    const liveRoomId = card.dataset.liveRoomId || '';
                    const likeBtn = card.querySelector('[data-action="like"]');
                    if (likeBtn) {
                        const label = likeBtn.querySelector('.nv-action-label, .nv-action-count, span');
                        results.push({
                            type, postId, id, liveRoomId,
                            liked: likeBtn.dataset.liked === 'true' || likeBtn.classList.contains('is-liked'),
                            dataset_liked: likeBtn.dataset.liked,
                            label: label ? label.textContent.trim() : '',
                            aria_pressed: likeBtn.getAttribute('aria-pressed'),
                            html: likeBtn.outerHTML.substring(0, 200),
                        });
                    }
                });
                return results;
            }
        """)
        log(f"  Total cards with like buttons: {len(card_info)}")
        for c in card_info:
            log(f"    type={c['type']:<10} postId={c['postId'][:20]:<22} id={c['id'][:20]:<22} liked={c['liked']} label={c['label'][:10]} dataset_liked={c['dataset_liked']} aria={c['aria_pressed']}")
        RESULTS["all_cards"] = card_info

        # Select a real post (data-type="post", has postId, not live_room)
        real_posts = [c for c in card_info if c["type"] == "post" and c["postId"] and c["id"]]
        if not real_posts:
            log("  No post cards found. Cannot continue.")
            await browser.close()
            return {"error": "No post cards"}

        selected = real_posts[0]
        selected_post = selected
        post_id = selected["postId"]
        log(f"\n  Selected: postId={post_id} type={selected['type']} liked={selected['liked']} label={selected['label']}")
        RESULTS["selected_post"] = selected

        # Also check the likes-state endpoint for this specific post
        ls_check = sess.get(
            f"{BASE_URL}/api/home/likes-state?type=post&ids={post_id}",
        )
        try:
            ls_check_data = ls_check.json()
            log(f"  Likes-state API for selected post: {json.dumps(ls_check_data, default=str)[:200]}")
            RESULTS["likes_state_direct_check"] = ls_check_data
        except:
            RESULTS["likes_state_direct_check"] = {"error": ls_check.text[:200]}

        # ── DB BEFORE first click ──────────────────────────────────
        log("\n--- DB BEFORE first click ---")
        with _init_db().app_context():
            post_rows = db_query(
                "SELECT id, profile_id, likes_count, comments_count, caption FROM chain_posts WHERE id = %s LIMIT 1",
                [post_id],
            )
            if post_rows:
                row = dict(post_rows[0])
                log(f"  chain_posts: likes_count={row.get('likes_count')}, comments_count={row.get('comments_count')}, profile_id={row.get('profile_id')}")
                db_before["chain_posts"] = {k: str(v) if hasattr(v,'isoformat') else v for k,v in row.items()}
            else:
                log(f"  No chain_posts row for {post_id}")
                db_before["chain_posts"] = None

            reaction_rows = db_query(
                "SELECT id, profile_id, post_id, reaction_type, created_at FROM chain_post_reactions WHERE post_id = %s AND reaction_type = 'like' ORDER BY created_at",
                [post_id],
            )
            log(f"  chain_post_reactions (all for post): {len(reaction_rows)} rows")
            for r in reaction_rows:
                log(f"    id={r['id'][:12]}... profile_id={r['profile_id'][:12]}...")
            db_before["chain_post_reactions"] = [dict(r) for r in reaction_rows]

            user_reaction = db_query(
                "SELECT id, profile_id, post_id, reaction_type FROM chain_post_reactions WHERE profile_id = %s AND post_id = %s AND reaction_type = 'like' LIMIT 1",
                [profile_id, post_id],
            )
            log(f"  Current user reaction: {len(user_reaction)} rows")
            db_before["user_reaction"] = [dict(r) for r in user_reaction]

            dup_check = db_query(
                "SELECT id FROM chain_post_reactions WHERE profile_id = %s AND post_id = %s AND reaction_type = 'like'",
                [profile_id, post_id],
            )
            db_before["user_reaction_dup_check"] = len(dup_check)
            log(f"  Duplicate reaction rows: {len(dup_check)}")

            post_owner = post_rows[0]["profile_id"] if post_rows else None
            db_before["post_owner_id"] = str(post_owner) if post_owner else None
            log(f"  Post owner: {post_owner}")
            log(f"  Current user: {profile_id}")
            log(f"  Self-like check: {str(post_owner) == profile_id if post_owner else 'N/A'}")

            # Check homepage payload for viewer_has_liked
            try:
                from services.homepage_phase141_service import fetch_feed_for_user
                items = fetch_feed_for_user(profile_id=profile_id, tab="for_you", page=1, limit=20, hard_fail=True)
                for item in items:
                    if str(item.get("id")) == post_id:
                        feed_before = {
                            "viewer_has_liked": item.get("viewer_has_liked"),
                            "is_liked": item.get("is_liked"),
                            "likes_count": item.get("likes_count"),
                            "user_liked": item.get("user_liked"),
                        }
                        log(f"  Feed payload: viewer_has_liked={item.get('viewer_has_liked')} is_liked={item.get('is_liked')} user_liked={item.get('user_liked')} likes_count={item.get('likes_count')}")
                        db_before["feed_item"] = feed_before
                        break
            except Exception as e:
                log(f"  Feed query unavailable: {e}")
                db_before["feed_item"] = {"error": str(e)}

        RESULTS["db_before"] = db_before

        # ── First like click ───────────────────────────────────────
        log("\n--- First like click ---")
        clear_network = ["like"]
        network_resps.clear()

        click_result = await page.evaluate("""
            (postId) => {
                const card = document.querySelector(`[data-post-id="${postId}"]`) ||
                            document.querySelector(`[data-id="${postId}"]`) ||
                            document.querySelector(`[data-item-id="${postId}"]`);
                if (!card) return { error: 'Card not found by any selector', postId };
                const likeBtn = card.querySelector('[data-action="like"]');
                if (!likeBtn) return { error: 'Like button not found' };
                likeBtn.click();
                return {
                    clicked: true,
                    dataset_liked_before: likeBtn.dataset.liked,
                    class_before: likeBtn.className,
                    likeBtnId: likeBtn.dataset.id || likeBtn.dataset.postId || '',
                };
            }
        """, post_id)
        log(f"  Click result: {click_result}")

        # Wait for API response
        await page.wait_for_timeout(4000)

        # Capture like responses
        like_resps = {k: v for k, v in network_resps.items()
                      if "like" in k.lower() and v.get("status")}
        for url, resp in like_resps.items():
            log(f"  Response: {resp.get('status')} {url}")
            if "body" in resp:
                log(f"    body: {json.dumps(resp['body'], default=str)[:300]}")
        http_first = list(like_resps.values())[0] if like_resps else {}
        RESULTS["http_first"] = http_first

        # ── UI after first click ───────────────────────────────────
        ui_after = await page.evaluate("""
            (postId) => {
                const card = document.querySelector(`[data-post-id="${postId}"]`) ||
                            document.querySelector(`[data-id="${postId}"]`) ||
                            document.querySelector(`[data-item-id="${postId}"]`);
                if (!card) return { error: 'Card not found after click' };
                const likeBtn = card.querySelector('[data-action="like"]');
                if (!likeBtn) return { error: 'Like button not found after click' };
                const label = likeBtn.querySelector('.nv-action-label, .nv-action-count, span');
                return {
                    liked: likeBtn.dataset.liked === 'true' || likeBtn.classList.contains('is-liked'),
                    classes: likeBtn.className,
                    dataset_liked: likeBtn.dataset.liked,
                    aria_pressed: likeBtn.getAttribute('aria-pressed'),
                    label: label ? label.textContent.trim() : '',
                };
            }
        """, post_id)
        log(f"  UI after first click: {ui_after}")
        ui_after_first = ui_after
        RESULTS["ui_after_first"] = ui_after

        # ── DB after first click ───────────────────────────────────
        log("\n--- DB AFTER first click ---")
        with _init_db().app_context():
            post_rows_after = db_query(
                "SELECT id, likes_count, comments_count FROM chain_posts WHERE id = %s LIMIT 1",
                [post_id],
            )
            if post_rows_after:
                row = dict(post_rows_after[0])
                log(f"  chain_posts likes_count: {row.get('likes_count')}")
                db_after_first["chain_posts"] = {k: str(v) if hasattr(v,'isoformat') else v for k,v in row.items()}

            user_reaction_after = db_query(
                "SELECT id, profile_id FROM chain_post_reactions WHERE profile_id = %s AND post_id = %s AND reaction_type = 'like' LIMIT 1",
                [profile_id, post_id],
            )
            log(f"  User reaction after: {len(user_reaction_after)} rows")
            db_after_first["user_reaction"] = [dict(r) for r in user_reaction_after]

        RESULTS["db_after_first"] = db_after_first

        await page.screenshot(path=str(SCREENSHOT_DIR / "namvibe_like_after_first.png"), full_page=True)

        # ── Refresh ────────────────────────────────────────────────
        log("\n--- Refresh homepage ---")
        network_resps.clear()
        await page.goto(f"{BASE_URL}/?e2e_no_refresh=1", wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)
        try:
            await page.wait_for_function(
                "window.NAMVIBE_HOME_INTERACTIONS_READY === true", timeout=10000,
            )
        except:
            pass
        await page.wait_for_timeout(2000)

        ui_refresh1 = await page.evaluate("""
            (postId) => {
                const card = document.querySelector(`[data-post-id="${postId}"]`) ||
                            document.querySelector(`[data-id="${postId}"]`) ||
                            document.querySelector(`[data-item-id="${postId}"]`);
                if (!card) return { error: 'Card not found after refresh' };
                const likeBtn = card.querySelector('[data-action="like"]');
                if (!likeBtn) return { error: 'Like btn not found' };
                const label = likeBtn.querySelector('.nv-action-label, .nv-action-count, span');
                return {
                    found: true,
                    liked: likeBtn.dataset.liked === 'true' || likeBtn.classList.contains('is-liked'),
                    dataset_liked: likeBtn.dataset.liked,
                    aria_pressed: likeBtn.getAttribute('aria-pressed'),
                    label: label ? label.textContent.trim() : '',
                };
            }
        """, post_id)
        log(f"  After refresh: {ui_refresh1}")
        ui_after_refresh1 = ui_refresh1
        RESULTS["ui_after_refresh1"] = ui_refresh1

        await page.screenshot(path=str(SCREENSHOT_DIR / "namvibe_like_after_refresh.png"), full_page=True)

        # ── Second click (unlike) ──────────────────────────────────
        log("\n--- Second click (unlike) ---")
        network_resps.clear()

        click_result2 = await page.evaluate("""
            (postId) => {
                const card = document.querySelector(`[data-post-id="${postId}"]`) ||
                            document.querySelector(`[data-id="${postId}"]`) ||
                            document.querySelector(`[data-item-id="${postId}"]`);
                if (!card) return { error: 'Card not found' };
                const likeBtn = card.querySelector('[data-action="like"]');
                if (!likeBtn) return { error: 'Like btn not found' };
                likeBtn.click();
                return { clicked: true, liked_before: likeBtn.dataset.liked };
            }
        """, post_id)
        log(f"  Click result: {click_result2}")
        await page.wait_for_timeout(4000)

        like_resps2 = {k: v for k, v in network_resps.items()
                       if "like" in k.lower() and v.get("status")}
        for url, resp in like_resps2.items():
            log(f"  Response: {resp.get('status')} {url}")
            if "body" in resp:
                log(f"    body: {json.dumps(resp['body'], default=str)[:300]}")
        http_second = list(like_resps2.values())[0] if like_resps2 else {}
        RESULTS["http_second"] = http_second

        ui_after_second_result = await page.evaluate("""
            (postId) => {
                const card = document.querySelector(`[data-post-id="${postId}"]`) ||
                            document.querySelector(`[data-id="${postId}"]`) ||
                            document.querySelector(`[data-item-id="${postId}"]`);
                if (!card) return { error: 'Card not found' };
                const likeBtn = card.querySelector('[data-action="like"]');
                if (!likeBtn) return { error: 'Like btn not found' };
                const label = likeBtn.querySelector('.nv-action-label, .nv-action-count, span');
                return {
                    liked: likeBtn.dataset.liked === 'true' || likeBtn.classList.contains('is-liked'),
                    dataset_liked: likeBtn.dataset.liked,
                    aria_pressed: likeBtn.getAttribute('aria-pressed'),
                    label: label ? label.textContent.trim() : '',
                };
            }
        """, post_id)
        log(f"  UI after second click: {ui_after_second_result}")
        ui_after_second = ui_after_second_result
        RESULTS["ui_after_second"] = ui_after_second

        await page.screenshot(path=str(SCREENSHOT_DIR / "namvibe_like_after_second.png"), full_page=True)

        # ── DB after second click ──────────────────────────────────
        log("\n--- DB AFTER second click ---")
        with _init_db().app_context():
            post_rows_after2 = db_query(
                "SELECT id, likes_count, comments_count FROM chain_posts WHERE id = %s LIMIT 1",
                [post_id],
            )
            if post_rows_after2:
                row = dict(post_rows_after2[0])
                log(f"  chain_posts likes_count: {row.get('likes_count')}")
                db_after_second["chain_posts"] = {k: str(v) if hasattr(v,'isoformat') else v for k,v in row.items()}

            user_reaction_after2 = db_query(
                "SELECT id, profile_id FROM chain_post_reactions WHERE profile_id = %s AND post_id = %s AND reaction_type = 'like' LIMIT 1",
                [profile_id, post_id],
            )
            log(f"  User reaction after second: {len(user_reaction_after2)} rows")
            db_after_second["user_reaction"] = [dict(r) for r in user_reaction_after2]

        RESULTS["db_after_second"] = db_after_second

        # ── Second refresh ─────────────────────────────────────────
        log("\n--- Refresh after unlike ---")
        await page.goto(f"{BASE_URL}/?e2e_no_refresh=1", wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)
        try:
            await page.wait_for_function(
                "window.NAMVIBE_HOME_INTERACTIONS_READY === true", timeout=10000,
            )
        except:
            pass
        await page.wait_for_timeout(2000)

        ui_refresh2 = await page.evaluate("""
            (postId) => {
                const card = document.querySelector(`[data-post-id="${postId}"]`) ||
                            document.querySelector(`[data-id="${postId}"]`) ||
                            document.querySelector(`[data-item-id="${postId}"]`);
                if (!card) return { error: 'Card not found' };
                const likeBtn = card.querySelector('[data-action="like"]');
                if (!likeBtn) return { error: 'Like btn not found' };
                const label = likeBtn.querySelector('.nv-action-label, .nv-action-count, span');
                return {
                    found: true,
                    liked: likeBtn.dataset.liked === 'true' || likeBtn.classList.contains('is-liked'),
                    dataset_liked: likeBtn.dataset.liked,
                    aria_pressed: likeBtn.getAttribute('aria-pressed'),
                    label: label ? label.textContent.trim() : '',
                };
            }
        """, post_id)
        log(f"  After second refresh: {ui_refresh2}")
        ui_after_refresh2 = ui_refresh2
        RESULTS["ui_after_refresh2"] = ui_refresh2

        # ── Browser console analysis ───────────────────────────────
        log(f"\n--- Console analysis ({len(all_console)} entries) ---")
        like_console = [c for c in all_console if "like" in c["text"].lower() or "NamVibe" in c["text"] or "heart" in c["text"].lower()]
        for c in like_console[-15:]:
            log(f"  [{c['type']}] {c['text'][:150]}")
        RESULTS["console_like"] = like_console[-15:]

        errors = [c for c in all_console if c["type"] in ("error", "page_error")]
        for e in errors:
            log(f"  PAGE ERROR: {e['text'][:200]}")
        RESULTS["console_errors"] = errors

        # Failed network requests
        RESULTS["network_errors"] = failed_reqs
        for f in failed_reqs:
            log(f"  FAILED: {f['method']} {f['url'][:100]} -> {f['failure'][:100]}")

        # ── Cache snapshot after ──────────────────────────────────
        cache_after = {}
        for k in list(cache_store.keys()):
            if "homepage" in k.lower() or "feed" in k.lower() or "like" in k.lower():
                cache_after[k] = str(type(cache_store[k]))
        RESULTS["cache_after"] = cache_after

        await browser.close()

    return compile_report()


def compile_report():
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_info": RESULTS.get("user_info", {}),
        "selected_post": RESULTS.get("selected_post", {}),
        "all_cards": RESULTS.get("all_cards", []),
        "db_before": RESULTS.get("db_before", {}),
        "http_first": RESULTS.get("http_first", {}),
        "db_after_first": RESULTS.get("db_after_first", {}),
        "ui_after_first": RESULTS.get("ui_after_first", {}),
        "ui_after_refresh1": RESULTS.get("ui_after_refresh1", {}),
        "http_second": RESULTS.get("http_second", {}),
        "db_after_second": RESULTS.get("db_after_second", {}),
        "ui_after_second": RESULTS.get("ui_after_second", {}),
        "ui_after_refresh2": RESULTS.get("ui_after_refresh2", {}),
        "cache_before": RESULTS.get("cache_before", {}),
        "cache_after": RESULTS.get("cache_after", {}),
        "console_errors": RESULTS.get("console_errors", []),
        "network_errors": RESULTS.get("network_errors", []),
        "console_like": RESULTS.get("console_like", []),
        "likes_state_calls": RESULTS.get("likes_state_calls", []),
        "likes_state_api_direct": RESULTS.get("likes_state_api_direct", {}),
        "likes_state_direct_check": RESULTS.get("likes_state_direct_check", {}),
    }


def print_report(report):
    print("\n" + "=" * 72)
    print("  NAMVIBE REAL LIKE PIPELINE AUDIT REPORT")
    print("=" * 72)
    u = report["user_info"]
    p = report["selected_post"]
    print(f"\n  User:              {u.get('email','?')}")
    print(f"  Profile ID:        {u.get('profile_id','?')}")
    print(f"  Post ID:           {p.get('postId','?')}")
    print(f"  Post type:         {p.get('type','?')}")

    db_b = report.get("db_before", {})
    print(f"\n  DB BEFORE:")
    print(f"    chain_posts:     {json.dumps(db_b.get('chain_posts',{}), default=str)}")
    print(f"    user_reaction:   {json.dumps(db_b.get('user_reaction',[]), default=str)}")
    print(f"    dup_check:       {db_b.get('user_reaction_dup_check','?')}")
    print(f"    feed:            {json.dumps(db_b.get('feed_item',{}), default=str)}")

    h1 = report.get("http_first", {})
    print(f"\n  FIRST CLICK HTTP:")
    print(f"    Status:          {h1.get('status','?')}")
    print(f"    Body:            {json.dumps(h1.get('body','?'), default=str)[:200]}")

    db_af1 = report.get("db_after_first", {})
    print(f"\n  DB AFTER FIRST:")
    print(f"    chain_posts:     {json.dumps(db_af1.get('chain_posts',{}), default=str)}")
    print(f"    user_reaction:   {json.dumps(db_af1.get('user_reaction',[]), default=str)}")

    ui1 = report.get("ui_after_first", {})
    print(f"\n  UI AFTER FIRST:    liked={ui1.get('liked','?')} label={ui1.get('label','?')}")

    ur1 = report.get("ui_after_refresh1", {})
    print(f"\n  REFRESH:           found={ur1.get('found','?')} liked={ur1.get('liked','?')} label={ur1.get('label','?')}")

    h2 = report.get("http_second", {})
    print(f"\n  SECOND CLICK HTTP:")
    print(f"    Status:          {h2.get('status','?')}")
    print(f"    Body:            {json.dumps(h2.get('body','?'), default=str)[:200]}")

    db_af2 = report.get("db_after_second", {})
    print(f"\n  DB AFTER SECOND:")
    print(f"    chain_posts:     {json.dumps(db_af2.get('chain_posts',{}), default=str)}")
    print(f"    user_reaction:   {json.dumps(db_af2.get('user_reaction',[]), default=str)}")

    ui2 = report.get("ui_after_second", {})
    print(f"\n  UI AFTER SECOND:   liked={ui2.get('liked','?')} label={ui2.get('label','?')}")

    ur2 = report.get("ui_after_refresh2", {})
    print(f"\n  REFRESH2:          found={ur2.get('found','?')} liked={ur2.get('liked','?')} label={ur2.get('label','?')}")

    print(f"\n  CACHE:             {len(report.get('cache_before',{}))} before, {len(report.get('cache_after',{}))} after (in-memory, no Redis)")
    print(f"  Network errors:    {len(report.get('network_errors',[]))}")
    print(f"  Console errors:    {len(report.get('console_errors',[]))}")

    ls_direct = report.get("likes_state_api_direct", {})
    print(f"\n  Likes-state API (direct): {json.dumps(ls_direct, default=str)[:150]}")

    ls_check = report.get("likes_state_direct_check", {})
    print(f"  Likes-state (selected post): {json.dumps(ls_check, default=str)[:150]}")

    # Summary
    db_feed = db_b.get("feed_item", {})
    ui_liked = ui1.get("liked")
    db_reaction = len(db_b.get("user_reaction", []))
    print(f"\n  === SUMMARY ===")
    print(f"  DB has reaction:       {'YES' if db_reaction > 0 else 'NO'}")
    print(f"  Feed viewer_has_liked: {db_feed.get('viewer_has_liked','N/A')}")
    print(f"  Feed is_liked:         {db_feed.get('is_liked','N/A')}")
    print(f"  UI shows liked:        {ui_liked}")
    print(f"  Click worked:          {'YES' if h1.get('status') else 'NO'}")
    print(f"  Network errors:        {len(report.get('network_errors',[]))}")
    print("=" * 72)


if __name__ == "__main__":
    log("=== NamVibe Real Like Pipeline Audit ===")
    log(f"Server: {BASE_URL}  User: {ALPHA_EMAIL}")
    _init_db()
    try:
        report = asyncio.run(audit())
        print_report(report)
        with open("/tmp/namvibe_like_audit_report.json", "w") as f:
            json.dump(report, f, default=str, indent=2)
        log(f"JSON: /tmp/namvibe_like_audit_report.json")
    except Exception as e:
        log(f"FATAL: {e}")
        traceback.print_exc()
        sys.exit(1)
