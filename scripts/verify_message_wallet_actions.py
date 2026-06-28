#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("FLASK_ENV", "development")

from app import create_app


def main():
    app = create_app()
    failures = []

    with app.test_client() as client:
        unauth = client.post("/messages/api/wallet/send", json={})
        if unauth.status_code != 302:
            failures.append("unauthenticated wallet send should redirect to login")

        with client.session_transaction() as sess:
            sess["auth_user_id"] = "11111111-1111-4111-8111-111111111111"
            sess["profile_id"] = "22222222-2222-4222-8222-222222222222"
            sess["user_id"] = "22222222-2222-4222-8222-222222222222"

        with patch("api_routes.message_routes.can_access_thread", return_value=True), \
             patch("api_routes.message_routes.phase29_messages.wallet_send", return_value={"ok": False, "error": "insufficient_balance"}), \
             patch("api_routes.message_routes.phase29_messages.wallet_tip", return_value={"ok": True, "transaction_id": "tip-1"}), \
             patch("api_routes.message_routes.phase29_messages.wallet_request", return_value={"ok": True, "request_id": "req-1"}), \
             patch("api_routes.message_routes.phase29_messages.wallet_split", return_value={"ok": True, "transfers": []}):
            send_fail = client.post("/messages/api/wallet/send", json={"thread_id": "t1", "recipient_profile_id": "33333333-3333-4333-8333-333333333333", "amount": 999})
            if send_fail.status_code != 200 or send_fail.get_json().get("error") != "insufficient_balance":
                failures.append("message wallet send should surface insufficient balance failure")

            tip_ok = client.post("/messages/api/wallet/tip", json={"thread_id": "t1", "recipient_profile_id": "33333333-3333-4333-8333-333333333333", "amount": 25, "idempotency_key": "tip-key"})
            if tip_ok.status_code != 200 or not tip_ok.get_json().get("ok"):
                failures.append("message wallet tip should return real success payload")

            request_ok = client.post("/messages/api/wallet/request", json={"thread_id": "t1", "recipient_profile_id": "33333333-3333-4333-8333-333333333333", "amount": 25, "idempotency_key": "req-key"})
            if request_ok.status_code != 200 or not request_ok.get_json().get("ok"):
                failures.append("message wallet request should return real success payload")

    if failures:
        print("FAIL")
        for failure in failures:
            print(failure)
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
