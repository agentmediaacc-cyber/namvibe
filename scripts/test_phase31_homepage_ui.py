#!/usr/bin/env python3
import os
import sys
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


def check(passed, label):
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {label}")
    return passed


def main():
    app.config["TESTING"] = True
    client = app.test_client()
    results = []

    print("\n=== Phase 31 Homepage UI Test ===\n")

    # Route rendering tests
    r = client.get("/", follow_redirects=True)
    results.append(check(r.status_code == 200, "GET / returns 200"))
    results.append(check(b"chain_home.html" not in r.data, "GET / renders template (not raw filename)"))

    r_disc = client.get("/discover/", follow_redirects=True)
    results.append(check(r_disc.status_code == 200, "GET /discover/ returns 200"))

    r_reels = client.get("/reels/", follow_redirects=True)
    results.append(check(r_reels.status_code == 200, "GET /reels/ returns 200"))

    r_status = client.get("/status/", follow_redirects=True)
    results.append(check(r_status.status_code == 200, "GET /status/ returns 200"))

    # Homepage key UI elements
    html = r.data.decode("utf-8")

    results.append(check(
        "chain-home__stories-section" in html or "Stories" in html,
        "Stories section present"
    ))
    results.append(check(
        "Trending Posts" in html or "chain-home__post-card" in html,
        "Feed/posts section present"
    ))
    results.append(check(
        "Fresh Reels" in html or "chain-home__reel-card" in html,
        "Reels section present"
    ))
    results.append(check(
        "Live Rooms" in html or "chain-home__live-card" in html,
        "Live rooms section present"
    ))
    results.append(check(
        "Recommended Profiles" in html or "chain-home__profile-card" in html,
        "Recommended profiles section present"
    ))
    results.append(check(
        "chain-home__menu-btn" in html or "social-menu-btn" in html or "menu-btn" in html,
        "Hamburger menu button present"
    ))
    results.append(check(
        "quick-nav" not in html and "quick-grid" not in html,
        "No dashboard-style quick grid present"
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
