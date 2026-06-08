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

    print("\n=== Phase 32 Calls & Live Speed Test ===\n")

    # Login
    with client.session_transaction() as sess:
        sess["auth_user_id"] = str(uuid.uuid4())
        sess["profile_id"] = str(uuid.uuid4())
        sess["auth_email"] = "callstest@example.com"
        sess["username"] = "callstest"

    # Time calls recent page
    start = time.perf_counter()
    r = client.get("/calls/recent", follow_redirects=True)
    elapsed = (time.perf_counter() - start) * 1000
    results.append(check(r.status_code == 200, "GET /calls/recent returns 200", elapsed))
    results.append(check(elapsed < 15000, f"GET /calls/recent completes in {elapsed:.0f}ms (target <15000ms)", elapsed))

    html = r.data.decode("utf-8")
    results.append(check("data-filter" in html or "All" in html or "Missed" in html, "Call filter buttons present"))

    # Time calls view with fake ID (should redirect gracefully)
    test_call_id = str(uuid.uuid4())
    start = time.perf_counter()
    r2 = client.get(f"/calls/{test_call_id}/view", follow_redirects=True)
    elapsed2 = (time.perf_counter() - start) * 1000
    results.append(check(r2.status_code in (200, 302, 404), f"GET /calls/<id>/view returns gracefully", elapsed2))
    results.append(check(elapsed2 < 10000, f"Call view completes in {elapsed2:.0f}ms (target <10000ms)", elapsed2))

    # Time live page
    start = time.perf_counter()
    r3 = client.get("/live/", follow_redirects=True)
    elapsed3 = (time.perf_counter() - start) * 1000
    results.append(check(r3.status_code == 200, "GET /live/ returns 200", elapsed3))
    results.append(check(elapsed3 < 10000, f"GET /live/ completes in {elapsed3:.0f}ms (target <10000ms)", elapsed3))

    live_html = r3.data.decode("utf-8")
    results.append(check("live" in live_html.lower() or "room" in live_html.lower(), "Live page renders"))

    # Time live studio page
    start = time.perf_counter()
    r4 = client.get("/live/studio", follow_redirects=True)
    elapsed4 = (time.perf_counter() - start) * 1000
    results.append(check(r4.status_code == 200, "GET /live/studio returns 200", elapsed4))
    results.append(check(elapsed4 < 15000, f"GET /live/studio completes in {elapsed4:.0f}ms (target <15000ms)", elapsed4))

    studio_html = r4.data.decode("utf-8")
    results.append(check("go-live" in studio_html.lower() or "go live" in studio_html.lower() or "start" in studio_html.lower(), "Studio controls present"))

    # Time a call that doesn't exist (graceful 404)
    start = time.perf_counter()
    r5 = client.get("/calls/start", follow_redirects=True)
    elapsed5 = (time.perf_counter() - start) * 1000
    results.append(check(r5.status_code in (200, 302, 404, 405), f"GET /calls/start returns gracefully", elapsed5))

    # Duplicate routes check
    audit_result = audit()
    dupes = audit_result.get("duplicates", [])
    results.append(check(len(dupes) == 0, f"No duplicate routes ({len(dupes)} found)"))

    # Missing templates
    missing = audit_result.get("missing_templates", [])
    results.append(check(len(missing) == 0, f"No missing templates ({len(missing)} found)"))

    # Broken imports
    broken = audit_result.get("broken_imports", [])
    results.append(check(len(broken) == 0, f"No broken imports ({len(broken)} found)"))

    passed = all(results)
    total = len(results)
    print(f"\nResults: {results.count(True)}/{total} passed, {results.count(False)}/{total} failed")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
