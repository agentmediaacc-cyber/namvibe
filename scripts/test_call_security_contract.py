#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    print(f"{status}: {label}" + (f" -- {detail}" if detail and not ok else ""))
    return ok


def fake_profile(profile_id: str):
    return {"id": profile_id, "username": f"user-{profile_id[:8]}", "display_name": "Test User"}


def main() -> int:
    from app import create_app
    import api_routes.call_routes as call_routes
    import services.friendship_service as friendship_service
    from services.call_permission_service import can_start_call, can_end_call

    ok = True

    ok &= check("self-call rejected", can_start_call("11111111-1111-4111-8111-111111111111", "11111111-1111-4111-8111-111111111111").get("error") == "self_call")
    ok &= check("missing caller rejected", can_start_call(None, "22222222-2222-4222-8222-222222222222").get("error") == "missing_profile")

    with patch("services.call_permission_service._get_profile_or_none", side_effect=lambda pid: fake_profile(pid)), \
         patch("services.call_permission_service._is_blocked", return_value=True):
        blocked = can_start_call("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222")
        ok &= check("blocked call rejected", not blocked.get("ok") and "blocked" in blocked.get("error", ""))

    call_obj = {"caller_profile_id": "11111111-1111-4111-8111-111111111111", "receiver_profile_id": "22222222-2222-4222-8222-222222222222"}
    ok &= check("participant can end", can_end_call(call_obj, call_obj["caller_profile_id"]))
    ok &= check("non-participant cannot end", not can_end_call(call_obj, "33333333-3333-4333-8333-333333333333"))

    app = create_app()
    app.config.update(TESTING=True)

    fake_result = {
        "ok": True,
        "call": {
            "id": "44444444-4444-4444-8444-444444444444",
            "caller_profile_id": "11111111-1111-4111-8111-111111111111",
            "receiver_profile_id": "22222222-2222-4222-8222-222222222222",
        },
    }

    with app.test_request_context("/api/calls/start", method="POST", json={"receiver_id": "22222222-2222-4222-8222-222222222222", "call_type": "video"}), \
         patch.object(call_routes, "get_current_profile", return_value=fake_profile("11111111-1111-4111-8111-111111111111")), \
         patch.object(friendship_service, "are_friends", return_value=True), \
         patch.object(call_routes, "w_create_call", return_value=fake_result) as create_mock, \
         patch.object(call_routes, "emit_activity"), \
         patch.object(call_routes, "track_interaction_safe"):
        response = app.make_response(call_routes.api_webrtc_start.__wrapped__())
        ok &= check("api start accepted", response.status_code == 200, str(response.status_code))
        data = response.get_json() or {}
        ok &= check("api start returns call payload", data.get("ok") is True and data.get("call", {}).get("id") == fake_result["call"]["id"], json.dumps(data, sort_keys=True))
        ok &= check("api start uses canonical creator", create_mock.call_count == 1, str(create_mock.call_count))

    with app.test_request_context("/api/calls/start", method="POST", json={"receiver_id": "22222222-2222-4222-8222-222222222222", "call_type": "video"}), \
        patch.object(call_routes, "get_current_profile", return_value=fake_profile("11111111-1111-4111-8111-111111111111")), \
        patch.object(friendship_service, "are_friends", return_value=False), \
        patch.object(call_routes, "w_create_call", return_value=fake_result) as create_mock:
        response = app.make_response(call_routes.api_webrtc_start.__wrapped__())
        ok &= check("unauthorized start blocked", response.status_code == 403, str(response.status_code))
        ok &= check("unauthorized start avoids call creation", create_mock.call_count == 0, str(create_mock.call_count))

    print("TEST_OK call security contract" if ok else "TEST_FAIL call security contract")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
