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
        with client.session_transaction() as sess:
            sess["auth_user_id"] = "11111111-1111-4111-8111-111111111111"
            sess["profile_id"] = "22222222-2222-4222-8222-222222222222"
            sess["user_id"] = "22222222-2222-4222-8222-222222222222"

        for route in (
            "/wallet/admin/api/payouts",
            "/wallet/admin/api/payouts/p1/approve",
            "/wallet/admin/api/payouts/p1/reject",
            "/wallet/admin/api/payouts/p1/mark-paid",
        ):
            method = client.get if route.endswith("/payouts") else client.post
            resp = method(route)
            if resp.status_code != 302:
                failures.append(f"non-admin should be rejected for {route}")

        with client.session_transaction() as sess:
            sess["admin_id"] = "admin-1"
            sess["admin_username"] = "admin"
            sess["admin_role"] = "admin"

        fake_admin = {"id": "admin-1", "username": "admin", "is_active": True, "role": "admin"}
        with patch("services.admin_auth_service.current_admin", return_value=fake_admin), \
             patch("api_routes.wallet_routes.get_payout_requests", return_value=[{"id": "p1", "status": "pending_review"}]), \
             patch("api_routes.wallet_routes.approve_payout", return_value={"ok": True, "status": "approved"}), \
             patch("api_routes.wallet_routes.reject_payout", return_value={"ok": True, "status": "rejected"}), \
             patch("api_routes.wallet_routes.mark_payout_paid", return_value={"ok": True, "status": "paid"}):
            list_resp = client.get("/wallet/admin/api/payouts")
            approve_resp = client.post("/wallet/admin/api/payouts/p1/approve", json={"admin_note": "ok"})
            reject_resp = client.post("/wallet/admin/api/payouts/p1/reject", json={"admin_note": "no"})
            paid_resp = client.post("/wallet/admin/api/payouts/p1/mark-paid")

            if list_resp.status_code != 200 or not list_resp.get_json().get("ok"):
                failures.append("admin payout list should succeed for admin")
            if approve_resp.status_code != 200 or approve_resp.get_json().get("status") != "approved":
                failures.append("admin approve should return approved")
            if reject_resp.status_code != 200 or reject_resp.get_json().get("status") != "rejected":
                failures.append("admin reject should return rejected")
            if paid_resp.status_code != 200 or paid_resp.get_json().get("status") != "paid":
                failures.append("admin mark-paid should return paid")

    if failures:
        print("FAIL")
        for failure in failures:
            print(failure)
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
