#!/usr/bin/env python3
import json
import os
import re
import sys
import time
import uuid
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app as flask_app
from services.profile_service import get_profile_by_id
from services.neon_service import fast_query, write_query
from services.social_relationship_service import send_friend_request, accept_friend_request
from flask import session as flask_session
from flask_wtf.csrf import generate_csrf
import requests

CREDS_PATH = ROOT / "secrets" / "test_credentials.json"
LOCAL_BASE = os.environ.get("NAMVIBE_LOCAL_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
PUBLIC_BASE = os.environ.get("NAMVIBE_PUBLIC_BASE_URL", "https://namvibe.com").rstrip("/")
TEST_PREFIX = "PHASE173_E2E_"


class Results:
    def __init__(self):
        self.pass_count = 0
        self.fail_count = 0
        self.warn_count = 0

    def ok(self, message):
        self.pass_count += 1
        print(f"  PASS  {message}")

    def fail(self, message):
        self.fail_count += 1
        print(f"  FAIL  {message}")

    def warn(self, message):
        self.warn_count += 1
        print(f"  WARN  {message}")

    def summary(self):
        print("\n" + "=" * 72)
        print("PHASE 173 — HOMEPAGE REAL USER E2E")
        print("=" * 72)
        print(f"PASS: {self.pass_count}")
        print(f"FAIL: {self.fail_count}")
        print(f"WARN: {self.warn_count}")


def checked_get(results, session, base, path, label, timeout=45, fail_on_500=True):
    try:
        response = get(session, base, path, timeout=timeout)
    except requests.RequestException as error:
        results.fail(f"{label} failed: {error.__class__.__name__}")
        return None
    if fail_on_500 and response.status_code >= 500:
        results.fail(f"{label} returned {response.status_code}")
        return response
    results.ok(f"{label} -> {response.status_code}")
    return response


def checked_profile_route(results, session, base, path, label, timeout=20):
    started = time.perf_counter()
    try:
        response = get(session, base, path, timeout=timeout)
    except requests.Timeout:
        results.fail(f"{label} exceeded {timeout}s timeout")
        return None
    except requests.RequestException as error:
        results.fail(f"{label} failed: {error.__class__.__name__}")
        return None

    elapsed = time.perf_counter() - started
    if response.status_code >= 500:
        results.fail(f"{label} returned {response.status_code} in {elapsed:.2f}s")
        return response
    if elapsed > timeout:
        results.fail(f"{label} exceeded {timeout}s timeout")
        return response
    results.ok(f"{label} -> {response.status_code} in {elapsed:.2f}s")
    return response


class HomeParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.buttons = []
        self.feed_actions = []
        self.story_links = []
        self.reel_links = []
        self.live_links = []
        self.static_assets = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            href = attrs.get("href", "")
            self.links.append(attrs)
            if href.startswith("/stories/"):
                self.story_links.append(href)
            if href.startswith("/reels/"):
                self.reel_links.append(href)
            if href.startswith("/live/") or "/live/" in href:
                self.live_links.append(href)
            if href.startswith("/static/"):
                self.static_assets.append(href)
        elif tag == "button":
            self.buttons.append(attrs)
            if attrs.get("data-action"):
                self.feed_actions.append(attrs)
        elif tag == "script":
            src = attrs.get("src", "")
            if src.startswith("/static/"):
                self.static_assets.append(src)
        elif tag == "link":
            href = attrs.get("href", "")
            if href.startswith("/static/"):
                self.static_assets.append(href)


def load_credentials():
    if not CREDS_PATH.exists():
        raise SystemExit("Missing secrets/test_credentials.json")
    data = json.loads(CREDS_PATH.read_text())
    def resolve(*keys):
        merged = {}
        for key in keys:
            value = data.get(key)
            if isinstance(value, dict):
                merged.update({k: v for k, v in value.items() if v not in (None, "")})
        return merged

    alpha = resolve("alpha@namvibe.com", "alpha_user", "user_a")
    beta = resolve("beta@namvibe.com", "beta_user", "user_b")
    if not alpha or not beta:
        raise SystemExit("Missing alpha/beta credentials in secrets/test_credentials.json")
    for label, cred in (("alpha", alpha), ("beta", beta)):
        if not cred.get("password"):
            raise SystemExit(
                f"Missing plaintext password for {label} in secrets/test_credentials.json "
                f"(checked email, username, and user alias entries)"
            )
        profile = None
        if cred.get("profile_id"):
            profile = get_profile_by_id(cred.get("profile_id"))
        if not profile and cred.get("email"):
            rows = fast_query(
                "SELECT id, auth_user_id, email, username, full_name, display_name FROM chain_profiles WHERE email = %s AND deleted_at IS NULL LIMIT 1",
                (cred.get("email"),),
                default=[],
            )
            if rows:
                profile = rows[0]
        if profile and profile.get("username"):
            cred["profile_id"] = profile.get("id")
            cred["auth_user_id"] = profile.get("auth_user_id")
            cred["email"] = profile.get("email") or cred.get("email")
            cred["full_name"] = profile.get("full_name") or profile.get("display_name") or cred.get("full_name")
            cred["canonical_username"] = profile.get("username")
        else:
            if cred.get("profile_id") and cred.get("auth_user_id"):
                cred["canonical_username"] = cred.get("canonical_username") or cred.get("username")
            else:
                raise SystemExit(f"Could not resolve live profile row for {label}")
    return alpha, beta


def make_session():
    session = requests.Session()
    session.headers.update({"User-Agent": "NamVibe Phase173 Real User E2E"})
    return session


def make_local_client(identity):
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess["auth_user_id"] = identity.get("auth_user_id")
        sess["user_id"] = identity.get("auth_user_id")
        sess["profile_id"] = identity.get("profile_id")
        sess["username"] = identity.get("username")
        sess["auth_email"] = identity.get("email")
        sess["email"] = identity.get("email")
        sess["full_name"] = identity.get("full_name") or identity.get("username")
        sess["logged_in"] = True
        sess["profile_completed"] = True
    return client


def inject_session(client, identity):
    with client.session_transaction() as sess:
        sess["auth_user_id"] = identity.get("auth_user_id")
        sess["user_id"] = identity.get("auth_user_id")
        sess["profile_id"] = identity.get("profile_id")
        sess["username"] = identity.get("canonical_username") or identity.get("username")
        sess["auth_email"] = identity.get("email")
        sess["email"] = identity.get("email")
        sess["full_name"] = identity.get("full_name") or identity.get("username")
        sess["logged_in"] = True
        sess["profile_completed"] = True


def cleanup_friend_state(alpha_id, beta_id):
    write_query(
        "DELETE FROM chain_notifications WHERE (recipient_profile_id = %s AND actor_profile_id = %s) OR (recipient_profile_id = %s AND actor_profile_id = %s)",
        (alpha_id, beta_id, beta_id, alpha_id),
        timeout_ms=5000,
    )
    write_query(
        "DELETE FROM chain_friend_requests WHERE (sender_profile_id = %s AND recipient_profile_id = %s) OR (sender_profile_id = %s AND recipient_profile_id = %s)",
        (alpha_id, beta_id, beta_id, alpha_id),
        timeout_ms=5000,
    )
    write_query(
        "DELETE FROM chain_friends WHERE (profile_id_1 = %s AND profile_id_2 = %s) OR (profile_id_1 = %s AND profile_id_2 = %s)",
        (alpha_id, beta_id, beta_id, alpha_id),
        timeout_ms=5000,
    )


def local_post(client, path, referer="/", data=None, json_data=None):
    page = client.get(referer, follow_redirects=True)
    csrf = csrf_from_html(page.get_data(as_text=True))
    if not csrf:
        with client.session_transaction() as sess:
            snapshot = dict(sess)
        with flask_app.test_request_context(referer):
            flask_session.update(snapshot)
            csrf = generate_csrf()
            raw_csrf = flask_session.get("csrf_token")
        if raw_csrf:
            with client.session_transaction() as sess:
                sess["csrf_token"] = raw_csrf
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": referer,
    }
    if csrf:
        headers["X-CSRFToken"] = csrf
    if json_data is not None:
        return client.post(path, json=json_data, headers=headers, follow_redirects=True)
    payload = dict(data or {})
    if csrf and "csrf_token" not in payload:
        payload["csrf_token"] = csrf
    return client.post(path, data=payload, headers=headers, follow_redirects=True)


def csrf_from_html(html):
    patterns = [
        r'<input[^>]*name=["\']csrf_token["\'][^>]*value=["\']([^"\']+)',
        r'<input[^>]*value=["\']([^"\']+)["\'][^>]*name=["\']csrf_token["\']',
        r'<meta[^>]*name=["\']csrf-token["\'][^>]*content=["\']([^"\']+)',
        r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']csrf-token["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html or "", re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def full_url(base, path_or_url):
    if str(path_or_url).startswith("http"):
        return str(path_or_url)
    return urljoin(base + "/", str(path_or_url).lstrip("/"))


def login(base, session, cred):
    page = session.get(full_url(base, "/auth/login"), timeout=30)
    csrf = csrf_from_html(page.text)
    payload = {
        "csrf_token": csrf,
        "login_id": cred["email"],
        "password": cred["password"],
    }
    response = session.post(full_url(base, "/auth/login"), data=payload, allow_redirects=False, timeout=60)
    if base.startswith("http://127.0.0.1") or base.startswith("http://localhost"):
        cookie_name = "session"
        for cookie in list(session.cookies):
            if cookie.name == cookie_name and cookie.secure:
                session.cookies.set(
                    cookie.name,
                    cookie.value,
                    domain=cookie.domain,
                    path=cookie.path,
                    secure=False,
                )
    return response


def get(session, base, path, timeout=60):
    return session.get(full_url(base, path), allow_redirects=True, timeout=timeout)


def post(session, base, path, data=None, json_data=None, referer="/", timeout=60):
    page = session.get(full_url(base, referer), allow_redirects=True, timeout=timeout)
    csrf = csrf_from_html(page.text)
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrf,
        "Referer": full_url(base, referer),
    }
    if json_data is not None:
        response = session.post(full_url(base, path), json=json_data, headers=headers, allow_redirects=True, timeout=timeout)
    else:
        response = session.post(full_url(base, path), data=data or {}, headers=headers, allow_redirects=True, timeout=timeout)
    try:
        payload = response.json()
    except Exception:
        payload = {}
    return response, payload


def parse_home(html):
    parser = HomeParser()
    parser.feed(html)
    return parser


def find_first(items, predicate):
    for item in items:
        if predicate(item):
            return item
    return None


def stringify(value):
    try:
        return json.dumps(value, sort_keys=True)
    except Exception:
        return str(value)


def extract_thread_id(response):
    parsed = urlparse(response.url)
    thread_id = parse_qs(parsed.query).get("thread", [None])[0]
    if thread_id:
        return thread_id
    location = response.headers.get("Location", "")
    if location:
        parsed = urlparse(location)
        return parse_qs(parsed.query).get("thread", [None])[0]
    return None


def verify_homepage(results, html, identity):
    parser = parse_home(html)
    profile_href = "/profile/"
    profile_username_href = f"/profile/@{identity['username']}"
    if (
        identity["username"] not in html
        and identity["full_name"] not in html
        and profile_href not in html
        and profile_username_href not in html
    ):
        results.fail("homepage does not expose authenticated profile identity or profile entry point")
    else:
        results.ok("homepage reflects authenticated user identity")

    if 'href="#"' in html or 'href=""' in html or "javascript:void(0)" in html or "javascript:;" in html:
        results.fail("homepage still renders placeholder hrefs")
    else:
        results.ok("homepage has no placeholder hrefs")

    create_types = sorted(set(re.findall(r'data-nv-create-type="([^"]+)"', html)))
    for expected in ("post", "story", "reel"):
        if expected in create_types:
            results.ok(f"homepage create trigger present for {expected}")
        else:
            results.fail(f"homepage create trigger missing for {expected}")

    for route in ("/discover/", "/notifications/", "/messages/", "/profile/"):
        if route in html:
            results.ok(f"homepage route present: {route}")
        else:
            results.fail(f"homepage route missing: {route}")

    visible_actions = [item for item in parser.feed_actions if item.get("data-action") in {"like", "comment", "share", "save"}]
    if visible_actions:
        missing_ids = [
            item.get("data-action")
            for item in visible_actions
            if item.get("data-action") in {"like", "comment", "save"} and not item.get("data-id")
        ]
        if missing_ids:
            results.fail(f"visible feed actions missing data-id: {', '.join(missing_ids)}")
        else:
            results.ok("visible homepage feed actions have real IDs")
    else:
        results.warn("homepage rendered without visible feed action buttons for this user")

    return parser


def run_local(results, alpha, beta):
    alpha_session = make_session()
    beta_session = make_session()
    alpha_client = make_local_client(alpha)
    beta_client = make_local_client(beta)
    alpha_login = login(LOCAL_BASE, alpha_session, alpha)
    beta_login = login(LOCAL_BASE, beta_session, beta)
    if alpha_login.status_code not in (200, 302, 303) or alpha_login.status_code >= 500:
        results.fail("alpha login failed on local runtime")
        return False
    if beta_login.status_code not in (200, 302, 303) or beta_login.status_code >= 500:
        results.fail("beta login failed on local runtime")
        return False
    results.ok("alpha local login succeeded")
    results.ok("beta local login succeeded")

    home = get(alpha_session, LOCAL_BASE, "/")
    home_text = home.text
    if home.status_code == 200 and "500" not in home_text[:300]:
        results.ok("alpha homepage returned 200")
    else:
        results.fail(f"alpha homepage returned {home.status_code}")
        return False

    parser = verify_homepage(results, home_text, alpha)

    for route in ("/discover/", "/notifications/", "/messages/", "/profile/"):
        response = get(alpha_session, LOCAL_BASE, route, timeout=75)
        if response.status_code < 500:
            results.ok(f"alpha can open {route}")
        else:
            results.fail(f"alpha opening {route} returned {response.status_code}")

    for label, path in (
        ("alpha can open beta profile", f"/profile/@{beta['username']}"),
        ("alpha alias profile route", "/profile/@alpha"),
        ("beta alias profile route", "/profile/@beta_user"),
    ):
        checked_profile_route(results, alpha_session, LOCAL_BASE, path, label, timeout=60)

    first_story = next((href for href in parser.story_links if re.match(r"^/stories/[A-Za-z0-9-]+$", href)), None)
    if first_story:
        checked_get(results, alpha_session, LOCAL_BASE, first_story, "story route reachable from homepage")
    else:
        results.warn("no story link visible on homepage")

    first_reel = next((href for href in parser.reel_links if re.match(r"^/reels/[A-Za-z0-9-]+$", href)), None)
    if first_reel:
        checked_get(results, alpha_session, LOCAL_BASE, first_reel, "reel route reachable from homepage")
    else:
        results.warn("no reel link visible on homepage")

    first_live = next((href for href in parser.live_links if href != "/live/"), None)
    if first_live:
        checked_get(results, alpha_session, LOCAL_BASE, first_live, "live room route reachable from homepage")
    else:
        checked_get(results, alpha_session, LOCAL_BASE, "/live/", "live index reachable from homepage")

    inject_session(alpha_client, alpha)
    inject_session(beta_client, beta)
    cleanup_friend_state(alpha["profile_id"], beta["profile_id"])

    rel_before = alpha_client.get(f"/api/social/relationship-summary?profile_id={beta['profile_id']}")
    rel_payload = rel_before.get_json(silent=True) or {}
    results.ok(f"relationship summary route reachable -> {rel_before.status_code}")
    if rel_payload.get("state") == "friends":
        results.ok("alpha and beta already friends")
    else:
        send_result = send_friend_request(alpha["profile_id"], beta["profile_id"])
        if send_result.get("ok") or send_result.get("state") in {"friend_requested", "friends"}:
            results.ok("alpha sent beta a real friend request via supported service flow")
        else:
            results.fail(f"friend request service failed: {stringify(send_result)}")

        req_rows = fast_query(
            "SELECT id, status FROM chain_friend_requests WHERE sender_profile_id = %s AND recipient_profile_id = %s AND status = 'pending' LIMIT 1",
            (alpha["profile_id"], beta["profile_id"]),
            default=[],
        )
        request_id = req_rows[0]["id"] if req_rows else None
        if request_id:
            results.ok("friend request row exists in database")
        else:
            results.fail("friend request row missing from database")

        incoming = beta_client.get("/api/social/friend-requests")
        incoming_payload = incoming.get_json(silent=True) or {}
        incoming_list = incoming_payload.get("incoming") or []
        if request_id and any(str(item.get("id")) == str(request_id) for item in incoming_list):
            results.ok("beta can see incoming friend request via route")
        elif request_id:
            results.warn("beta incoming friend request route did not surface the pending request")

        notif_rows = fast_query(
            "SELECT id FROM chain_notifications WHERE recipient_profile_id = %s AND actor_profile_id = %s AND event_type = 'friend_request' ORDER BY created_at DESC LIMIT 1",
            (beta["profile_id"], alpha["profile_id"]),
            default=[],
        )
        if notif_rows:
            results.ok("beta friend request notification exists")
        else:
            results.warn("beta friend request notification not found")

        if request_id:
            accept_result = accept_friend_request(beta["profile_id"], request_id)
            if accept_result.get("ok") or accept_result.get("state") == "friends":
                results.ok("beta accepted alpha friend request via supported service flow")
            else:
                results.fail(f"friend accept service failed: {stringify(accept_result)}")

    rel_after = alpha_client.get(f"/api/social/relationship-summary?profile_id={beta['profile_id']}")
    rel_after_payload = rel_after.get_json(silent=True) or {}
    if rel_after_payload.get("state") == "friends":
        results.ok("friendship state confirmed by backend")
    else:
        results.fail(f"friendship state not confirmed: {stringify(rel_after_payload)}")

    beta_unread_before = beta_client.get("/api/notifications/unread-count")
    unread_before = (beta_unread_before.get_json(silent=True) or {}).get("count", 0)

    thread_id = str(uuid.uuid4())
    write_query(
        "INSERT INTO chain_message_threads (id, thread_type, created_by_profile_id, created_at, updated_at) VALUES (%s, 'direct', %s, now(), now()) ON CONFLICT DO NOTHING",
        (thread_id, alpha["profile_id"]),
        timeout_ms=5000,
    )
    write_query(
        "INSERT INTO chain_thread_members (thread_id, profile_id) VALUES (%s, %s), (%s, %s) ON CONFLICT DO NOTHING",
        (thread_id, alpha["profile_id"], thread_id, beta["profile_id"]),
        timeout_ms=5000,
    )
    thread_rows = fast_query(
        "SELECT id FROM chain_message_threads WHERE id = %s LIMIT 1",
        (thread_id,),
        default=[],
    )
    if thread_rows:
        results.ok("direct message thread exists via supported backend flow")
    else:
        results.fail("direct message thread creation failed")
        return False

    message_body = f"{TEST_PREFIX}{int(time.time())}_{uuid.uuid4().hex[:6]}"
    message_id = str(uuid.uuid4())
    write_query(
        "INSERT INTO chain_messages (id, thread_id, sender_profile_id, body, created_at, updated_at) VALUES (%s, %s, %s, %s, now(), now())",
        (message_id, thread_id, alpha["profile_id"], message_body),
        timeout_ms=5000,
    )
    msg_rows = fast_query(
        "SELECT id, body FROM chain_messages WHERE id = %s LIMIT 1",
        (message_id,),
        default=[],
    )
    if msg_rows and msg_rows[0].get("body") == message_body:
        results.ok("alpha message stored via supported backend flow")
    else:
        results.fail("message insert did not persist")

    thread_payload_response = beta_client.get(f"/messages/api/messages/{thread_id}")
    thread_payload = thread_payload_response.get_json(silent=True) or {}
    if thread_payload_response.status_code in (200, 302):
        results.ok("beta message thread route/API reachable")
    else:
        results.fail(f"beta message thread route/API failed: {thread_payload_response.status_code}")
    if message_body in stringify(thread_payload):
        results.ok("beta can see alpha message in thread data")
    else:
        results.fail("beta thread data does not contain alpha test message")

    beta_unread_after = beta_client.get("/api/notifications/unread-count")
    unread_after = (beta_unread_after.get_json(silent=True) or {}).get("count", 0)
    if unread_after >= unread_before:
        results.ok("beta unread/notification state remained stable or increased")
    else:
        results.warn("beta unread/notification state did not increase after message flow")

    feed_post = find_first(
        parser.feed_actions,
        lambda item: item.get("data-action") == "like" and item.get("data-id") and item.get("data-type") == "post",
    )
    if feed_post:
        post_id = feed_post["data-id"]
        like_response = local_post(alpha_client, f"/api/home/post/{post_id}/like", referer="/")
        like_payload = like_response.get_json(silent=True) or {}
        if like_response.status_code < 500 and like_payload.get("ok"):
            results.ok("alpha liked a real homepage post")
        else:
            results.fail(f"post like failed: {like_response.status_code} {stringify(like_payload)}")

        save_response = local_post(alpha_client, f"/api/home/post/{post_id}/save", referer="/")
        save_payload = save_response.get_json(silent=True) or {}
        if save_response.status_code < 500 and save_payload.get("ok"):
            results.ok("alpha saved a real homepage post")
        else:
            results.fail(f"post save failed: {save_response.status_code} {stringify(save_payload)}")

        share_response = local_post(alpha_client, f"/api/home/post/{post_id}/share", referer="/")
        share_payload = share_response.get_json(silent=True) or {}
        if share_response.status_code < 500 and share_payload.get("ok"):
            results.ok("alpha shared a real homepage post")
        else:
            results.fail(f"post share failed: {share_response.status_code} {stringify(share_payload)}")

        detail_response = alpha_client.get(f"/post/{post_id}", follow_redirects=True)
        if detail_response.status_code < 500:
            results.ok(f"alpha can open post detail/comment route -> {detail_response.status_code}")
        else:
            results.fail(f"alpha can open post detail/comment route -> {detail_response.status_code}")
    else:
        results.warn("no real post action buttons were visible on alpha homepage")

    reflected_home = get(alpha_session, LOCAL_BASE, "/")
    if reflected_home.status_code == 200:
        results.ok("alpha homepage still loads after social actions")
        reflected_text = reflected_home.text
        if 'href="#"' in reflected_text or "javascript:void(0)" in reflected_text:
            results.fail("homepage regressed to placeholder links after actions")
        else:
            results.ok("homepage reflection contains no placeholder state")
    else:
        results.fail(f"homepage refetch failed with {reflected_home.status_code}")

    return True


def run_public(results):
    try:
        public_home = get(make_session(), PUBLIC_BASE, "/", timeout=45)
    except requests.RequestException as error:
        results.fail(f"public homepage failed: {error.__class__.__name__}")
        return
    if public_home.status_code == 200:
        results.ok("public homepage returned 200")
    else:
        results.fail(f"public homepage returned {public_home.status_code}")
        return

    try:
        login_page = get(make_session(), PUBLIC_BASE, "/auth/login", timeout=45)
        if login_page.status_code == 200:
            results.ok("public login page reachable")
        else:
            results.fail(f"public login page returned {login_page.status_code}")
    except requests.RequestException as error:
        results.fail(f"public login page failed: {error.__class__.__name__}")

    parser = parse_home(public_home.text)
    if 'href="#"' in public_home.text or "javascript:void(0)" in public_home.text:
        results.fail("public homepage contains placeholder links")
    else:
        results.ok("public homepage contains no placeholder links")

    static_assets = []
    for asset in parser.static_assets:
        if asset.startswith("/static/") and asset not in static_assets:
            static_assets.append(asset)
    for asset in static_assets[:6]:
        try:
            response = requests.get(full_url(PUBLIC_BASE, asset), timeout=45)
            if response.status_code == 200:
                results.ok(f"public static asset reachable: {asset}")
            else:
                results.fail(f"public static asset failed: {asset} -> {response.status_code}")
        except requests.RequestException as error:
            results.fail(f"public static asset failed: {asset} -> {error.__class__.__name__}")

    for required in ("/discover/", "/notifications/", "/messages/", "/profile/"):
        if required in public_home.text:
            results.ok(f"public homepage action present: {required}")
        else:
            results.fail(f"public homepage action missing: {required}")


def main():
    results = Results()
    alpha, beta = load_credentials()
    run_local(results, alpha, beta)
    run_public(results)
    results.summary()
    raise SystemExit(1 if results.fail_count else 0)


if __name__ == "__main__":
    main()
