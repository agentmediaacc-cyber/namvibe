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

    print("\n=== Phase 32 Homepage Speed Test ===\n")

    # Login
    with client.session_transaction() as sess:
        sess["auth_user_id"] = str(uuid.uuid4())
        sess["profile_id"] = str(uuid.uuid4())
        sess["auth_email"] = "speedtest@example.com"
        sess["username"] = "speedtest"

    # Time homepage render
    start = time.perf_counter()
    r = client.get("/", follow_redirects=True)
    elapsed = (time.perf_counter() - start) * 1000
    results.append(check(r.status_code == 200, "GET / returns 200", elapsed))
    results.append(check(elapsed < 10000, f"GET / completes in {elapsed:.0f}ms (target <10000ms)", elapsed))

    html = r.data.decode("utf-8")
    results.append(check("chain_home" in html or "stories" in html, "Homepage template renders"))
    results.append(check("hamburger" in html.lower() or "menu" in html.lower() or "drawer" in html.lower(), "Hamburger menu present"))

    # Time discover page
    start = time.perf_counter()
    r2 = client.get("/discover/", follow_redirects=True)
    elapsed2 = (time.perf_counter() - start) * 1000
    results.append(check(r2.status_code == 200, "GET /discover/ returns 200", elapsed2))
    results.append(check(elapsed2 < 10000, f"GET /discover/ completes in {elapsed2:.0f}ms (target <10000ms)", elapsed2))

    # Time reels page
    start = time.perf_counter()
    r3 = client.get("/reels/", follow_redirects=True)
    elapsed3 = (time.perf_counter() - start) * 1000
    results.append(check(r3.status_code == 200, "GET /reels/ returns 200", elapsed3))
    results.append(check(elapsed3 < 10000, f"GET /reels/ completes in {elapsed3:.0f}ms (target <10000ms)", elapsed3))

    # Time status page
    start = time.perf_counter()
    r4 = client.get("/status/", follow_redirects=True)
    elapsed4 = (time.perf_counter() - start) * 1000
    results.append(check(r4.status_code == 200, "GET /status/ returns 200", elapsed4))
    results.append(check(elapsed4 < 10000, f"GET /status/ completes in {elapsed4:.0f}ms (target <10000ms)", elapsed4))

    # Check no missing templates
    audit_result = audit()
    missing = audit_result.get("missing_templates", [])
    results.append(check(len(missing) == 0, f"No missing templates ({len(missing)} found)"))

    # Check no broken imports
    broken = audit_result.get("broken_imports", [])
    results.append(check(len(broken) == 0, f"No broken imports ({len(broken)} found)"))

    # Check no broken url_for
    broken_url = audit_result.get("broken_url_for", [])
    results.append(check(len(broken_url) == 0, f"No broken url_for ({len(broken_url)} found)"))

    passed = all(results)
    total = len(results)
    print(f"\nResults: {results.count(True)}/{total} passed, {results.count(False)}/{total} failed")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
