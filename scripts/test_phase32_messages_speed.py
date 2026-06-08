#!/usr/bin/env python3
import os
import sys
import time
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


def check(passed, label, elapsed_ms=None):
    status = "PASS" if passed else "FAIL"
    extra = f" ({elapsed_ms:.0f}ms)" if elapsed_ms is not None else ""
    print(f"  [{status}] {label}{extra}")
    return passed


def main():
    from app import app
    from scripts.audit_chain_routes import audit

    app.config["TESTING"] = True
    client = app.test_client()
    results = []

    print("\n=== Phase 32 Messages Speed Test ===\n")

    # Login
    with client.session_transaction() as sess:
        sess["auth_user_id"] = str(uuid.uuid4())
        sess["profile_id"] = str(uuid.uuid4())
        sess["auth_email"] = "msgspeed@example.com"
        sess["username"] = "msgspeed"

    # Time messages inbox
    start = time.perf_counter()
    r = client.get("/messages/", follow_redirects=True)
    elapsed = (time.perf_counter() - start) * 1000
    results.append(check(r.status_code == 200, "GET /messages/ returns 200", elapsed))
    results.append(check(elapsed < 15000, f"GET /messages/ completes in {elapsed:.0f}ms (target <15000ms)", elapsed))

    html = r.data.decode("utf-8")
    results.append(check("messages" in html.lower() or "inbox" in html.lower() or "chat" in html.lower(), "Messages page renders"))

    # Time thread page (fake ID, should 302 gracefully)
    test_thread_id = str(uuid.uuid4())
    start = time.perf_counter()
    r2 = client.get(f"/messages/thread/{test_thread_id}", follow_redirects=True)
    elapsed2 = (time.perf_counter() - start) * 1000
    results.append(check(r2.status_code in (200, 302, 404), f"GET /messages/thread/<id> returns gracefully", elapsed2))
    results.append(check(elapsed2 < 10000, f"Thread page completes in {elapsed2:.0f}ms (target <10000ms)", elapsed2))

    # Time messages API
    start = time.perf_counter()
    r3 = client.get("/messages/api/messages/threads")
    elapsed3 = (time.perf_counter() - start) * 1000
    results.append(check(r3.status_code == 200, "GET /messages/api/messages/threads returns 200", elapsed3))
    results.append(check(elapsed3 < 5000, f"API threads completes in {elapsed3:.0f}ms (target <5000ms)", elapsed3))

    # Check templates render
    results.append(check("thread-card" in html or "thread" in html.lower(), "Thread list references exist"))

    # Call a few key page urls and verify they render
    for path, name in [
        ("/profile/", "Profile page"),
        ("/wallet/", "Wallet page"),
    ]:
        start = time.perf_counter()
        rp = client.get(path, follow_redirects=True)
        ep = (time.perf_counter() - start) * 1000
        results.append(check(rp.status_code in (200, 302, 404), f"GET {path} returns gracefully", ep))

    passed = all(results)
    total = len(results)
    print(f"\nResults: {results.count(True)}/{total} passed, {results.count(False)}/{total} failed")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
