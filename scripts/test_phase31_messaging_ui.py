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
        sess["auth_email"] = "msgtest@example.com"
        sess["username"] = "msgtest"
        sess["full_name"] = "Message Tester"


def check(passed, label):
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {label}")
    return passed


def main():
    app.config["TESTING"] = True
    client = app.test_client()
    results = []

    print("\n=== Phase 31 Messaging UI Test ===\n")

    # Route tests (need auth)
    _login(client)
    r_inbox = client.get("/messages/", follow_redirects=True)
    results.append(check(r_inbox.status_code == 200, "GET /messages/ returns 200"))

    test_thread_id = str(uuid.uuid4())
    r_thread = client.get(f"/messages/thread/{test_thread_id}", follow_redirects=False)
    results.append(check(
        r_thread.status_code in (200, 302, 404),
        f"GET /messages/thread/<id> returns {r_thread.status_code} (200/302/404 graceful)"
    ))

    html = r_inbox.data.decode("utf-8")

    # Key messaging UI elements
    results.append(check(
        "pinned" in html.lower() or "chain-msg-pinned" in html or "Pin Message" in html,
        "Pinned message element referenced"
    ))
    results.append(check(
        "data-message-select" in html or "data-msg-id" in html or "msg-select-cb" in html,
        "Multi-select checkbox element present"
    ))
    results.append(check(
        "forward" in html.lower() or "Forward" in html or "initForward" in html,
        "Forward modal/drawer present"
    ))
    results.append(check(
        "attach-item" in html or "attachMenu" in html or "attach-menu" in html,
        "Attach menu with media/docs/links present"
    ))
    results.append(check(
        "voice-preview" in html or "voicePreview" in html,
        "Voice preview card present"
    ))
    results.append(check(
        "emoji-panel" in html or "emojiPanel" in html,
        "Emoji panel present"
    ))
    results.append(check(
        "presence-text" in html or "chat-header-sub" in html or "thread-online-dot" in html or "chat-online-dot" in html,
        "Online/offline indicator present"
    ))

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
