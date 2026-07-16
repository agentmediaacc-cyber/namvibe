#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import services.profile_service as profile_service


def main() -> int:
    calls = {}

    def fake_fast_query(sql, params=None, timeout_ms=None, default=None):
        calls["params"] = list(params or [])
        return [{"id": calls["params"][0], "username": "valid"}] if calls["params"] else []

    original = profile_service.fast_query
    profile_service.fast_query = fake_fast_query
    try:
        result = profile_service.batch_get_profiles([
            "prof-1",
            "11111111-1111-1111-1111-111111111111",
            "not-a-uuid",
        ])
    finally:
        profile_service.fast_query = original

    assert calls.get("params") == ["11111111-1111-1111-1111-111111111111"], calls
    assert "11111111-1111-1111-1111-111111111111" in result, result
    print("TEST_OK profile uuid filter contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
