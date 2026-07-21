#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    print(f"{status}: {label}" + (f" -- {detail}" if detail and not ok else ""))
    return ok


def main() -> int:
    import services.subscription_entitlement_service as ses

    ok = True
    with patch("services.subscription_entitlement_service.get_pool_status", return_value={"pool_ready": False, "recent_success": False, "configured": False}):
        free = ses.get_entitlement("u1")
    ok &= check("db unavailable returns safe free default", free["effective_plan"] == "free" and free["is_premium"] is False, str(free))

    with patch("services.subscription_entitlement_service.get_pool_status", return_value={"pool_ready": True, "recent_success": True, "configured": True}), \
         patch("services.subscription_entitlement_service.fast_query", return_value=[{"premium_tier": "pro", "status": "active", "starts_at": "2026-07-01T00:00:00+00:00", "expires_at": "2026-08-01T00:00:00+00:00"}]):
        active = ses.get_entitlement("u2")
    ok &= check("active subscription remains premium", active["is_premium"] is True and active["effective_plan"] == "pro", str(active))

    with patch("services.subscription_entitlement_service.get_pool_status", return_value={"pool_ready": True, "recent_success": True, "configured": True}), \
         patch("services.subscription_entitlement_service.fast_query", return_value=[{"premium_tier": "pro", "status": "active", "expires_at": "2020-01-01T00:00:00+00:00"}]):
        expired = ses.get_entitlement("u3")
    ok &= check("expired subscription becomes free", expired["is_premium"] is False and expired["effective_plan"] == "free", str(expired))

    print("TEST_OK subscription integrity contract" if ok else "TEST_FAIL subscription integrity contract")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
