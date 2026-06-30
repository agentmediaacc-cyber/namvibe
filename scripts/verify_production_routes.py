#!/usr/bin/env python3
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("FLASK_ENV", "development")

from app import create_app


TEST_AUTH_USER_ID = "11111111-1111-4111-8111-111111111111"
TEST_PROFILE_ID = "22222222-2222-4222-8222-222222222222"
TEST_EMAIL = "route-check@example.com"
TEST_USERNAME = "routecheck"
TEST_PROFILE_DATA = {
    "id": TEST_PROFILE_ID,
    "auth_user_id": TEST_AUTH_USER_ID,
    "email": TEST_EMAIL,
    "username": TEST_USERNAME,
    "display_name": "Route Check",
    "full_name": "Route Check",
    "avatar_url": "",
    "is_verified": False,
    "verified": False,
    "profile_completed": True,
}


PUBLIC_ROUTES = [
    "/",
    "/home",
    "/login",
    "/register",
    "/feed",
    "/reels",
    "/stories",
    "/search",
    "/terms",
    "/privacy",
    "/healthz",
]

AUTH_ROUTES = [
    "/messages/",
    "/notifications/",
    "/notifications/center",
    "/calls/recent",
    "/wallet/",
    "/settings",
]


def check(response, allowed, label, failures):
    if response.status_code not in allowed:
        failures.append(f"{label}: expected {sorted(allowed)}, got {response.status_code}")


def main():
    app = create_app()
    failures = []

    with app.test_client() as client:
        for route in PUBLIC_ROUTES:
            check(client.get(route), {200, 302}, f"GET {route}", failures)

        for route in AUTH_ROUTES:
            check(client.get(route), {302}, f"GET {route} unauth", failures)

        api_unauth_checks = [
            ("/calls/api/history", {302}),
        ]
        for route, allowed in api_unauth_checks:
            check(client.get(route), allowed, f"GET {route} unauth", failures)

        with client.session_transaction() as sess:
            sess["auth_user_id"] = TEST_AUTH_USER_ID
            sess["profile_id"] = TEST_PROFILE_ID
            sess["user_id"] = TEST_PROFILE_ID
            sess["auth_email"] = TEST_EMAIL
            sess["email"] = TEST_EMAIL
            sess["username"] = TEST_USERNAME
            sess["full_name"] = "Route Check"
            sess["profile_completed"] = True
            sess["profile_data"] = dict(TEST_PROFILE_DATA)

        for route in AUTH_ROUTES:
            check(client.get(route), {200, 302}, f"GET {route} auth", failures)

        api_checks = [
            ("/api/stories/feed", {200}),
            ("/calls/api/history", {200}),
            ("/api/notifications/unread-count", {200}),
            ("/api/notifications/center/unread-count", {200}),
            ("/wallet/api/transactions", {200}),
        ]
        for route, allowed in api_checks:
            check(client.get(route), allowed, f"GET {route} auth", failures)

    if failures:
        print("FAIL")
        for item in failures:
            print(item)
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
