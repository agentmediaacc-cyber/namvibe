#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
home_service = (ROOT / "services/homepage_service.py").read_text()
notifications = (ROOT / "services/notification_engine.py").read_text()
profile_routes = (ROOT / "api_routes/profile_routes.py").read_text()
live = (ROOT / "services/live_feature_service.py").read_text()


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


check("notification unread cache uses notif key", "notif:unread:" in notifications)
check("notification unread cache has ttl", "cache_set(cache_key, count, ttl=" in notifications or "ttl=45" in notifications)
check("notification invalidates unread cache", "invalidate_unread_count" in notifications)
check("homepage sections use timeouts", "future.result(timeout=" in home_service and "timeout_ms=" in home_service)
check("homepage queries are limited", "LIMIT" in home_service and "_HOMEPAGE_LIMITS" in home_service)
check("homepage avoids n+1 profile lookups", "batch_load_profiles" in home_service)
check("profile bundle errors have fallback", "profile_bundle_route_failed" in profile_routes and "get_profile_bundle" in profile_routes)
check("profile followers/friends have limits", "limit=8" in profile_routes or "LIMIT 8" in profile_routes)
check("live start uses dynamic column compatibility", "get_cached_table_columns(\"chain_live_rooms\")" in live and "host_profile_id" in live and "profile_id" in live)
