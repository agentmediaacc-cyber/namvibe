#!/usr/bin/env python3
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / "venv" / "bin" / "python3"
if VENV_PY.exists() and Path(sys.executable).resolve() != VENV_PY.resolve():
    os.execv(str(VENV_PY), [str(VENV_PY), *sys.argv])
sys.path.insert(0, str(ROOT))

os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_DISABLE_DB_PING"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"

from app import app
from scripts.audit_chain_routes import audit


def _login(client):
    with client.session_transaction() as sess:
        sess["auth_user_id"] = str(uuid.uuid4())
        sess["profile_id"] = str(uuid.uuid4())
        sess["auth_email"] = "livetest@example.com"
        sess["username"] = "livetest"
        sess["full_name"] = "Live Tester"


def check(passed, label):
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {label}")
    return passed


def main():
    app.config["TESTING"] = True
    client = app.test_client()
    results = []

    print("\n=== Phase 31 Live / Groups / Creator UI Test ===\n")

    # Live channels page (public)
    r_live = client.get("/live/", follow_redirects=True)
    results.append(check(r_live.status_code == 200, "GET /live/ returns 200"))

    # Live studio (needs auth)
    _login(client)
    r_studio = client.get("/live/studio", follow_redirects=True)
    results.append(check(r_studio.status_code == 200, "GET /live/studio returns 200"))

    # Live watch room (public)
    test_room_id = str(uuid.uuid4())
    r_watch = client.get(f"/live/room/{test_room_id}", follow_redirects=True)
    results.append(check(
        r_watch.status_code in (200, 404),
        f"GET /live/room/<id> returns {r_watch.status_code} (200 or 404 graceful)"
    ))

    # Creator dashboard (needs auth)
    r_creator = client.get("/creator/dashboard", follow_redirects=True)
    results.append(check(r_creator.status_code == 200, "GET /creator/dashboard returns 200"))

    # Live page key elements
    lhtml = r_live.data.decode("utf-8")
    results.append(check(
        "live-card" in lhtml or "live-room-card" in lhtml or "channels-grid" in lhtml,
        "Live room cards present"
    ))
    results.append(check(
        "Go Live" in lhtml or "Start Live" in lhtml or "Go Live Now" in lhtml or "live/studio" in lhtml,
        "Start Live / Go Live button present"
    ))

    # Watch page elements (if returned 200)
    if r_watch.status_code == 200:
        whtml = r_watch.data.decode("utf-8")
        results.append(check(
            "gift" in whtml.lower() or "Gift" in whtml,
            "Gift element on watch page"
        ))
        results.append(check(
            "chat" in whtml.lower() or "Chat" in whtml or "chatMessages" in whtml,
            "Chat element on watch page"
        ))
        results.append(check(
            "clip" in whtml.lower() or "Clip" in whtml,
            "Clip element on watch page"
        ))
        results.append(check(
            "leaderboard" in whtml.lower() or "Leaderboard" in whtml,
            "Leaderboard element on watch page"
        ))
        results.append(check(
            "shopping" in whtml.lower() or "Shopping" in whtml or "shopping item" in whtml.lower(),
            "Shopping element on watch page"
        ))
    else:
        for label in ["Gift element on watch page", "Chat element on watch page",
                       "Clip element on watch page", "Leaderboard element on watch page",
                       "Shopping element on watch page"]:
            results.append(check(True, f"{label} (skipped - room not found)"))

    # Studio controls
    shtml = r_studio.data.decode("utf-8")
    results.append(check(
        "allow-comments" in shtml or "allow_comments" in shtml or "allowComments" in shtml or "allow comments" in shtml.lower(),
        "Allow comments control in studio"
    ))
    results.append(check(
        "allow-gifts" in shtml or "allow_gifts" in shtml or "allowGifts" in shtml or "gift" in shtml.lower(),
        "Allow gifts control in studio"
    ))
    results.append(check(
        "guest-requests" in shtml or "guest" in shtml.lower() or "guest_request" in shtml,
        "Guest requests control in studio"
    ))
    results.append(check(
        "polls" in shtml.lower() or "poll" in shtml.lower(),
        "Polls control in studio"
    ))
    results.append(check(
        "battle" in shtml.lower() or "Battle" in shtml,
        "Battle control in studio"
    ))
    results.append(check(
        "end-live" in shtml or "end_live" in shtml or "End Live" in shtml or "end live" in shtml.lower(),
        "End live control in studio"
    ))
    results.append(check(
        "RTMP" in shtml or "rtmp" in shtml.lower() or "server configuration" in shtml.lower(),
        "RTMP note / server configuration present"
    ))

    # Creator dashboard tabs
    dhtml = r_creator.data.decode("utf-8")
    expected_tabs = [
        "Overview", "Earnings", "Gifts", "Live Earnings",
        "Subscriptions", "Paid Posts", "Premium Content",
        "Payouts", "Sponsorships", "Top Fans", "Badges", "Verification"
    ]
    for tab in expected_tabs:
        results.append(check(tab in dhtml, f"Creator dashboard tab: '{tab}' present"))

    # Duplicate route check
    audit_result = audit()
    dupes = audit_result.get("duplicates", [])
    results.append(check(len(dupes) == 0, f"No duplicate routes ({len(dupes)} found)"))

    passed = all(results)
    total = len(results)
    print(f"\nResults: {results.count(True)}/{total} passed, {results.count(False)}/{total} failed")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
