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


def check(response, allowed, label, failures):
    if response.status_code not in allowed:
        failures.append(f"{label}: expected {sorted(allowed)}, got {response.status_code}")


def main():
    app = create_app()
    failures = []

    with app.test_client() as client:
        check(client.get("/wallet/"), {302}, "GET /wallet/ unauth", failures)
        check(client.get("/wallet/api/balance"), {302}, "GET /wallet/api/balance unauth", failures)

        with client.session_transaction() as sess:
            sess["auth_user_id"] = TEST_AUTH_USER_ID
            sess["profile_id"] = TEST_PROFILE_ID
            sess["user_id"] = TEST_PROFILE_ID

        check(client.get("/wallet/"), {200}, "GET /wallet/ auth", failures)
        check(client.get("/wallet/withdraw"), {200}, "GET /wallet/withdraw auth", failures)
        check(client.get("/wallet/transactions"), {200}, "GET /wallet/transactions auth", failures)
        check(client.get("/wallet/payouts"), {200}, "GET /wallet/payouts auth", failures)

        check(client.get("/wallet/api/balance"), {200, 404}, "GET /wallet/api/balance auth", failures)
        check(client.get("/wallet/api/transactions"), {200}, "GET /wallet/api/transactions auth", failures)
        check(client.get("/wallet/api/summary"), {200, 404}, "GET /wallet/api/summary auth", failures)
        check(client.get("/wallet/api/gifts"), {200}, "GET /wallet/api/gifts", failures)
        check(client.get("/wallet/api/wallet/balance-summary"), {200}, "GET /wallet/api/wallet/balance-summary auth", failures)
        check(client.get("/wallet/api/wallet/earnings-breakdown"), {200}, "GET /wallet/api/wallet/earnings-breakdown auth", failures)
        check(client.get("/wallet/api/wallet/payout-methods"), {200}, "GET /wallet/api/wallet/payout-methods auth", failures)

        check(
            client.post("/wallet/api/wallet/deposit", json={"amount_cents": 100}),
            {200, 400},
            "POST /wallet/api/wallet/deposit auth",
            failures,
        )
        check(
            client.post("/wallet/api/payouts/request", json={"amount_cents": 100}),
            {200, 400},
            "POST /wallet/api/payouts/request auth",
            failures,
        )
        check(
            client.post("/wallet/api/wallet/payout-methods", json={"provider": "bank", "account_name": "Test User", "masked_account": "****1234"}),
            {200, 400},
            "POST /wallet/api/wallet/payout-methods auth",
            failures,
        )

    if failures:
        print("FAIL")
        for item in failures:
            print(item)
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
