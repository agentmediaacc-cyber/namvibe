import os
import re
import sys
from pathlib import Path


os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402


MENU_RE = re.compile(
    r'<nav class="nv-mobile-menu-links"[^>]*>(?P<body>.*?)</nav>',
    re.IGNORECASE | re.DOTALL,
)
LINK_RE = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>\s*([^<]+?)\s*</a>', re.IGNORECASE)


def _extract_menu_links(html):
    match = MENU_RE.search(html)
    assert match, "mobile menu nav not found"
    body = match.group("body")
    links = {}
    for href, label in LINK_RE.findall(body):
        links[label.strip()] = href.strip()
    return links


def _assert_okish(client, path):
    resp = client.get(path, follow_redirects=False)
    assert resp.status_code in {200, 301, 302, 303, 307, 308}, f"{path} returned {resp.status_code}"
    assert resp.status_code != 500, f"{path} returned 500"
    assert resp.status_code != 404, f"{path} returned 404"


def _render_menu(client, logged_in=False):
    if logged_in:
        with client.session_transaction() as sess:
            sess["profile_id"] = "menu-test-user"
            sess["auth_user_id"] = "menu-test-user"
    resp = client.get("/")
    assert resp.status_code == 200, f"homepage returned {resp.status_code}"
    return _extract_menu_links(resp.get_data(as_text=True))


def main():
    public_expected = {
        "Home": "/",
        "Discover": "/discover/",
        "Reels": "/reels/",
        "Stories": "/stories/",
        "Live": "/live/",
        "Support": "/support",
        "Terms": "/terms",
        "Privacy": "/privacy",
    }
    logged_out_auth = "/auth/login"
    private_logged_out = {
        "Messages": logged_out_auth,
        "Calls": logged_out_auth,
        "Wallet": logged_out_auth,
        "Notifications": logged_out_auth,
        "Profile": logged_out_auth,
        "Settings": logged_out_auth,
    }
    private_logged_in = {
        "Messages": "/messages/",
        "Calls": "/calls/",
        "Wallet": "/wallet/",
        "Notifications": "/notifications/",
        "Profile": "/profile/",
        "Settings": "/profile/settings",
    }

    with app.test_client() as client:
        logged_out_links = _render_menu(client, logged_in=False)
        for label, href in public_expected.items():
            assert logged_out_links.get(label) == href, f"logged-out {label} href mismatch: {logged_out_links.get(label)}"
            _assert_okish(client, href)
        for label, href in private_logged_out.items():
            assert logged_out_links.get(label) == href, f"logged-out {label} href mismatch: {logged_out_links.get(label)}"
            _assert_okish(client, href)

    with app.test_client() as client:
        logged_in_links = _render_menu(client, logged_in=True)
        for label, href in public_expected.items():
            assert logged_in_links.get(label) == href, f"logged-in {label} href mismatch: {logged_in_links.get(label)}"
        for label, href in private_logged_in.items():
            assert logged_in_links.get(label) == href, f"logged-in {label} href mismatch: {logged_in_links.get(label)}"
            _assert_okish(client, href)

    print("hamburger menu production: ok")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"hamburger menu production: FAIL - {exc}")
        sys.exit(1)
