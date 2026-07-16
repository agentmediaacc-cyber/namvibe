#!/usr/bin/env python3
"""Deterministic contract for friend-request notification navigation."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import services.friend_service as friend_service


def check(name, condition):
    print(("PASS" if condition else "FAIL") + f": {name}")
    if not condition:
        raise AssertionError(name)


def main():
    captured = []

    def fake_get_profile_by_id(profile_id):
        profiles = {
            "sender-1": {"id": "sender-1", "username": "alpha", "display_name": "Alpha"},
            "accepter-1": {"id": "accepter-1", "username": "beta", "display_name": "Beta"},
        }
        return profiles.get(profile_id)

    def fake_create_notification(*args, **kwargs):
        captured.append({"args": args, "kwargs": kwargs})
        return "notif-1"

    original_get_profile_by_id = friend_service.get_profile_by_id
    original_create_notification = friend_service.create_notification
    try:
        friend_service.get_profile_by_id = fake_get_profile_by_id
        friend_service.create_notification = fake_create_notification

        friend_service._notify_friend_request("sender-1", "recipient-1")
        friend_service._notify_friend_accepted("accepter-1", "sender-1")

        check("two notifications captured", len(captured) == 2)
        request_kwargs = captured[0]["kwargs"]
        accept_kwargs = captured[1]["kwargs"]

        check("friend request uses canonical sender profile url", request_kwargs.get("action_url") == "/profile/@alpha")
        check("friend accepted uses canonical accepter profile url", accept_kwargs.get("action_url") == "/profile/@beta")
        check("friend request does not use raw numeric path", "/profile/" not in request_kwargs.get("action_url", "") or "@alpha" in request_kwargs.get("action_url", ""))
        check("friend accepted does not use raw numeric path", "/profile/" not in accept_kwargs.get("action_url", "") or "@beta" in accept_kwargs.get("action_url", ""))
        print("test_friend_notification_navigation_contract_ok")
    finally:
        friend_service.get_profile_by_id = original_get_profile_by_id
        friend_service.create_notification = original_create_notification


if __name__ == "__main__":
    main()
