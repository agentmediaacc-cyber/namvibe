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
    with patch("app.check_ip_reputation", side_effect=AssertionError("check_ip_reputation should not run for /api/feed/check")):
        response = client.get("/api/feed/check")
    body = response.get_json()
    check("feed check status", response.status_code == 200, response.status_code)
    check("feed check payload", body["ok"] is True and body["has_new"] is False, body)
    print("OK")


if __name__ == "__main__":
    main()
