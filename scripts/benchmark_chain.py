#!/usr/bin/env python
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ.setdefault("CHAIN_TEST_FAKE_DB", "1")

import app as _app_module
from app import create_app


def _fake_profile():
    return {"id": "benchmark-profile", "username": "benchmark", "profile_fallback": False}


def measure(client, method, path, samples=3):
    values = []
    for _ in range(samples):
        start = time.perf_counter()
        getattr(client, method.lower())(path)
        values.append((time.perf_counter() - start) * 1000)
    return {"path": path, "avg_ms": round(statistics.mean(values), 2), "max_ms": round(max(values), 2)}


def main():
    app = create_app()
    _app_module.get_current_profile = _fake_profile
    try:
        import services.profile_service as _profile_service
        import api_routes.message_production_routes as _message_production_routes
        _profile_service.get_current_profile = _fake_profile
        _message_production_routes.get_current_profile = _fake_profile
    except Exception:
        pass
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["profile_id"] = "benchmark-profile"
        sess["auth_user_id"] = "benchmark-profile"
        sess["user_id"] = "benchmark-profile"
    checks = [
        ("get", "/healthz"),
        ("get", "/messages/api/unread-count"),
        ("get", "/wallet/api/balance"),
        ("get", "/calls/api/active"),
        ("get", "/safety/api/trust-summary"),
        ("get", "/system/api/queue/stats"),
    ]
    report = [measure(client, method, path) for method, path in checks]
    print("CHAIN benchmark report")
    for item in report:
        print(f"{item['path']}: avg={item['avg_ms']}ms max={item['max_ms']}ms")


if __name__ == "__main__":
    main()
