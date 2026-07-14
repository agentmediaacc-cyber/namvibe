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


SNAPSHOT = {
    "feed_items": [{"id": "post-1", "privacy": "public"}],
    "posts": [{"id": "post-1", "privacy": "public"}],
    "reels": [{"id": "reel-1", "privacy": "public"}],
    "stories": [{"id": "story-1", "privacy": "public"}],
    "live_rooms": [{"id": "live-1", "privacy": "public"}],
    "suggested_creators": [{"id": "creator-1", "username": "publiccreator"}],
    "suggested_people": [{"id": "creator-1", "username": "publiccreator"}],
    "trending_hashtags": [{"tag": "namvibe"}],
    "online_users": [],
    "counts": {"live_now": 1, "unread_messages": 0, "coins": 0},
    "homepage_degraded": False,
    "timings": {},
}


def main():
    client = app.test_client()
    with patch("api_routes.homepage_api.get_full", return_value=dict(SNAPSHOT)), \
         patch("api_routes.homepage_api.get_payload", return_value=None), \
         patch("api_routes.homepage_api._build_homepage_contract", side_effect=AssertionError("builder should not run on cached widgets")), \
         patch("api_routes.homepage_api._get_homepage_widgets", side_effect=AssertionError("anon cached widgets should not fetch heavy widget data")):
        response = client.get("/api/homepage/widgets")
    body = response.get_json()
    check("homepage widgets status", response.status_code == 200, response.status_code)
    check("homepage widgets cached", body["ok"] is True and body["live_rooms"][0]["id"] == "live-1", body)
    check("wallet omitted/empty", body["wallet"]["coin_balance"] == 0, body)
    print("OK")


if __name__ == "__main__":
    main()
