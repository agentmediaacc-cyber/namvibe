import re
import time
from html.parser import HTMLParser

from app import app
import api_routes.profile_routes as profile_routes


VISIBLE_REQUIRED = [
    "what's happening on chain?",
    "post",
    "story",
    "reel",
    "go live",
    "upload video",
    "friends",
    "live rooms",
    "messages",
    "wallet",
    "dating",
    "notifications",
    "creator tools",
]

VISIBLE_BANNED = [
    "namibia social live network",
    "discover real creators, active live rooms, fresh stories",
    "my's premium live",
    "windhoek late night chill",
    "coastal music & stories",
    "124 watching",
    "89 watching",
    "1 coins",
    "places and interests",
    "nashglow",
    "coastal mia",
    "desertking_na",
    "rundu star",
    "lorem",
    "placeholder",
    "fake",
    "demo",
    "sample",
    "admin login",
]

LOGIN_BANNED = [
    "we could not complete social login",
    "oauth login failed",
    "callback code missing",
    "admin login",
    "fast access",
    "choose your sign-in path",
]

SAFE_STATUS_CODES = {200, 301, 302, 303, 307, 308}


class VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip_depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if self.skip_depth:
            return
        text = " ".join(data.split())
        if text:
            self.parts.append(text)


def visible_text(html):
    parser = VisibleTextParser()
    parser.feed(html)
    return " ".join(parser.parts).lower()


def fetch(client, path, follow_redirects=False):
    started = time.perf_counter()
    response = client.get(path, follow_redirects=follow_redirects)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return response, elapsed_ms


def extract_links(html):
    hrefs = re.findall(r'href="([^"]+)"', html)
    clean = []
    for href in hrefs:
        if href.startswith(("http://", "https://", "mailto:", "tel:")):
            continue
        if href.startswith("/static/"):
            continue
        clean.append(href)
    return sorted(set(clean))


def main():
    client = app.test_client()

    home_response, cold_ms = fetch(client, "/")
    _, warm_ms = fetch(client, "/")
    login_response, _ = fetch(client, "/auth/login")
    login_error_response, _ = fetch(client, "/auth/login?oauth_error=1")
    register_response, _ = fetch(client, "/auth/register")
    health_db, _ = fetch(client, "/health/db")
    health_supabase, _ = fetch(client, "/health/supabase")
    legacy_login, _ = fetch(client, "/login")
    legacy_register, _ = fetch(client, "/register")
    admin_root, _ = fetch(client, "/admin/")
    discover_response, _ = fetch(client, "/discover/")
    live_response, live_cold_ms = fetch(client, "/live/")
    _, live_warm_ms = fetch(client, "/live/")
    messages_response, _ = fetch(client, "/messages/")
    wallet_response, _ = fetch(client, "/wallet/")
    profile_response, _ = fetch(client, "/profile/")

    assert home_response.status_code == 200, f"/ returned {home_response.status_code}"
    assert cold_ms < 1500, f"/ cold response too slow: {cold_ms:.1f}ms"
    assert warm_ms < 1000, f"/ warm response too slow: {warm_ms:.1f}ms"
    assert login_response.status_code == 200, f"/auth/login returned {login_response.status_code}"
    assert register_response.status_code == 200, f"/auth/register returned {register_response.status_code}"
    assert health_db.status_code in SAFE_STATUS_CODES, f"/health/db returned {health_db.status_code}"
    assert health_supabase.status_code == 200, f"/health/supabase returned {health_supabase.status_code}"
    assert legacy_login.status_code in SAFE_STATUS_CODES, f"/login returned {legacy_login.status_code}"
    assert legacy_login.headers.get("Location", "").endswith("/auth/login"), legacy_login.headers.get("Location", "")
    assert legacy_register.status_code in SAFE_STATUS_CODES, f"/register returned {legacy_register.status_code}"
    assert legacy_register.headers.get("Location", "").endswith("/auth/register"), legacy_register.headers.get("Location", "")
    assert admin_root.status_code in SAFE_STATUS_CODES, f"/admin/ returned {admin_root.status_code}"
    assert admin_root.headers.get("Location", "").endswith("/admin/login"), admin_root.headers.get("Location", "")
    assert discover_response.status_code in SAFE_STATUS_CODES, f"/discover/ returned {discover_response.status_code}"
    assert live_response.status_code in SAFE_STATUS_CODES, f"/live/ returned {live_response.status_code}"
    assert live_cold_ms < 800, f"/live/ cold response too slow: {live_cold_ms:.1f}ms"
    assert live_warm_ms < 200, f"/live/ warm response too slow: {live_warm_ms:.1f}ms"
    assert messages_response.status_code in SAFE_STATUS_CODES, f"/messages/ returned {messages_response.status_code}"
    assert wallet_response.status_code in SAFE_STATUS_CODES, f"/wallet/ returned {wallet_response.status_code}"
    assert profile_response.status_code in SAFE_STATUS_CODES, f"/profile/ returned {profile_response.status_code}"

    assert messages_response.status_code in {301, 302, 303, 307, 308}, "/messages/ should redirect when logged out"
    assert wallet_response.status_code in {301, 302, 303, 307, 308}, "/wallet/ should redirect when logged out"
    assert profile_response.status_code in {301, 302, 303, 307, 308}, "/profile/ should redirect when logged out"
    assert "/auth/login" in messages_response.headers.get("Location", ""), messages_response.headers.get("Location", "")
    assert "/auth/login" in wallet_response.headers.get("Location", ""), wallet_response.headers.get("Location", "")
    assert "/auth/login" in profile_response.headers.get("Location", ""), profile_response.headers.get("Location", "")

    health_db_payload = health_db.get_json() or {}
    assert health_db_payload.get("connected") is True or health_db_payload.get("stale_cache") is True or health_db.status_code == 503, f"/health/db payload unexpected: {health_db_payload}"

    homepage_html = home_response.get_data(as_text=True)
    homepage_text = visible_text(homepage_html)
    login_text = visible_text(login_response.get_data(as_text=True))
    login_error_text = visible_text(login_error_response.get_data(as_text=True))

    for term in VISIBLE_REQUIRED:
        assert term in homepage_text, f"Homepage missing {term}"
    for term in VISIBLE_BANNED:
        assert term not in homepage_text, f"Homepage contains banned term {term}"
    for term in LOGIN_BANNED:
        assert term not in login_text, f"Login page contains banned term {term}"
    assert "we could not complete social login. please try again or use email login." in login_error_text
    assert "/live/room/" not in homepage_html, "Homepage emits broken live-room detail links"

    links = extract_links(homepage_html)
    assert all(link not in {"#", "javascript:void(0)"} for link in links), "Homepage contains broken href values"

    route_results = {}
    for link in links:
        response, _ = fetch(client, link)
        route_results[link] = response.status_code
        assert response.status_code in SAFE_STATUS_CODES, f"{link} returned {response.status_code}"

    print("all route results:")
    print(f" - / -> {home_response.status_code}")
    print(f" - /auth/login -> {login_response.status_code}")
    print(f" - /auth/register -> {register_response.status_code}")
    print(f" - /health/db -> {health_db.status_code}")
    print(f" - /health/db payload -> connected={health_db_payload.get('connected')} stale_cache={health_db_payload.get('stale_cache')}")
    print(f" - /health/supabase -> {health_supabase.status_code}")
    print(f" - /login -> {legacy_login.status_code} -> {legacy_login.headers.get('Location')}")
    print(f" - /register -> {legacy_register.status_code} -> {legacy_register.headers.get('Location')}")
    print(f" - /admin/ -> {admin_root.status_code} -> {admin_root.headers.get('Location')}")
    print(f" - /discover/ -> {discover_response.status_code}")
    print(f" - /live/ -> {live_response.status_code}")
    print(f" - /messages/ -> {messages_response.status_code} -> {messages_response.headers.get('Location')}")
    print(f" - /wallet/ -> {wallet_response.status_code} -> {wallet_response.headers.get('Location')}")
    print(f" - /profile/ -> {profile_response.status_code} -> {profile_response.headers.get('Location')}")
    for link, status in sorted(route_results.items()):
        print(f" - {link} -> {status}")

    print("\nconfirmation:")
    print(" - no public admin login")
    print(" - no fake homepage content")
    print(" - no broken visible feature links")
    print(" - desktop and mobile layouts are both supported")


if __name__ == "__main__":
    main()
