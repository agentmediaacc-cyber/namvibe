#!/usr/bin/env python3
import os
import sys
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")

from app import app


def check(name, condition, detail=""):
    print(("PASS" if condition else "FAIL"), name)
    if not condition:
        raise AssertionError(detail or name)


def main():
    client = app.test_client()
    with patch("app.check_ip_reputation", side_effect=AssertionError("IP reputation hook should be skipped")), \
         patch("app.refresh_chain_session", side_effect=AssertionError("session refresh should be skipped")):
        health = client.get("/healthz")
        feed_check = client.get("/api/feed/check")
        ai_status = client.get("/api/ai/status")
        homepage_feed = client.get("/api/homepage/feed")

    check("health ok", health.status_code == 200, health.status_code)
    check("feed check ok", feed_check.status_code == 200, feed_check.status_code)
    check("ai status auth or cache path ok", ai_status.status_code in {200, 401}, ai_status.status_code)
    check("homepage feed ok", homepage_feed.status_code == 200, homepage_feed.status_code)
    print("OK")


if __name__ == "__main__":
    main()
