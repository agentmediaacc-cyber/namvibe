#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from unittest.mock import Mock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")


def _reset_refresh_state(warmup_module):
    with warmup_module._REFRESH_LOCK:  # noqa: SLF001 - intentional test access
        warmup_module._REFRESH_IN_FLIGHT = False  # noqa: SLF001 - intentional test access
        warmup_module._REFRESH_EVENT.set()  # noqa: SLF001 - intentional test access


def main() -> int:
    import app as app_module
    from services import homepage_warmup_service as warmup_module

    _reset_refresh_state(warmup_module)

    class FakeThread:
        started = 0
        daemon_values = []
        targets = []

        def __init__(self, target=None, daemon=None):
            self.target = target
            self.daemon = daemon
            FakeThread.targets.append(target)
            FakeThread.daemon_values.append(daemon)

        def start(self):
            FakeThread.started += 1

    with patch.object(warmup_module.threading, "Thread", FakeThread):
        scheduled = warmup_module.schedule_homepage_refresh()
        assert scheduled is True
        assert warmup_module.is_homepage_refresh_in_flight() is True
        assert warmup_module.wait_for_homepage_refresh(timeout_seconds=0.01) is False
        assert FakeThread.started == 1
        assert FakeThread.daemon_values == [True]

        second = warmup_module.schedule_homepage_refresh()
        assert second is False
        assert FakeThread.started == 1

    _reset_refresh_state(warmup_module)

    with patch.object(warmup_module, "warm_homepage_cache", return_value={"ok": True}):
        warmup_module._REFRESH_IN_FLIGHT = True  # noqa: SLF001 - intentional test access
        warmup_module._REFRESH_EVENT.clear()  # noqa: SLF001 - intentional test access
        warmup_module._refresh_worker()
        assert warmup_module.is_homepage_refresh_in_flight() is False
        assert warmup_module.wait_for_homepage_refresh(timeout_seconds=0.01) is False

    _reset_refresh_state(warmup_module)

    with patch.object(warmup_module, "warm_homepage_cache", side_effect=RuntimeError("boom")):
        warmup_module._REFRESH_IN_FLIGHT = True  # noqa: SLF001 - intentional test access
        warmup_module._REFRESH_EVENT.clear()  # noqa: SLF001 - intentional test access
        warmup_module._refresh_worker()
        assert warmup_module.is_homepage_refresh_in_flight() is False
        assert warmup_module.wait_for_homepage_refresh(timeout_seconds=0.01) is False
        assert warmup_module.wait_for_homepage_refresh(timeout_seconds=0.0) is False

    stale_payload = {
        "feed_items": [{"id": "post-1"}],
        "posts": [{"id": "post-1"}],
        "reels": [{"id": "reel-1"}],
        "stories": [],
        "live_rooms": [],
        "suggested_creators": [],
        "suggested_people": [],
        "trending_hashtags": [],
        "online_users": [],
        "friend_activity": [],
        "counts": {"online_count": 0, "live_count": 0},
        "wallet": {"coin_balance": 0},
        "homepage_degraded": False,
        "timings": {"posts": 1.0, "reels": 1.0},
    }

    with app_module.app.test_request_context("/"):
        with patch.object(app_module, "get_full_with_stale", return_value=(dict(stale_payload), True)), \
             patch.object(app_module, "schedule_homepage_refresh", return_value=True) as schedule_mock, \
             patch.object(app_module, "wait_for_homepage_refresh", side_effect=AssertionError("stale content should not block on refresh")), \
             patch.object(app_module, "_app_test_mode", return_value=False), \
             patch.object(app_module, "set_local_cache"), \
             patch.object(app_module, "render_template", return_value="<html>ok</html>"), \
             patch("api_routes.homepage_api._build_homepage_contract", side_effect=AssertionError("stale homepage should not rebuild")), \
             patch.object(app_module, "log_info"), \
             patch.object(app_module, "log_warning"), \
             patch.object(app_module, "log_error"):
            response = app_module.app.view_functions["home"]()

        assert response.status_code == 200
        assert schedule_mock.call_count == 1

    with app_module.app.test_request_context("/"):
        with patch.object(app_module, "get_full_with_stale", return_value=(None, False)), \
             patch.object(app_module, "wait_for_homepage_refresh", return_value=True), \
             patch.object(app_module, "set_local_cache"), \
             patch.object(app_module, "render_template", return_value="<html>ok</html>"), \
             patch("api_routes.homepage_api._build_homepage_contract", return_value={
                 "feed_items": [{"id": "post-2"}],
                 "posts": [{"id": "post-2"}],
                 "reels": [{"id": "reel-2"}],
                 "stories": [],
                 "live_rooms": [],
                 "suggested_creators": [],
                 "suggested_people": [],
                 "trending_hashtags": [],
                 "online_users": [],
                 "friend_activity": [],
                 "counts": {"online_count": 0, "live_count": 0},
                 "wallet": {"coin_balance": 0},
                 "homepage_degraded": False,
                 "timings": {},
             }) as build_mock, \
             patch.object(app_module, "log_info"), \
             patch.object(app_module, "log_warning"), \
             patch.object(app_module, "log_error"):
            response = app_module.app.view_functions["home"]()

        assert response.status_code == 200
        assert build_mock.call_count == 1

    with patch("api_routes.homepage_api.fetch_stories_v2", return_value=([], False, None)), \
         patch("api_routes.homepage_api.fetch_posts_v2", side_effect=lambda *args, **kwargs: ([], False, None) if kwargs.get("include_ads") is False else (_ for _ in ()).throw(AssertionError("cold warmup should disable feed ads"))), \
         patch("api_routes.homepage_api.fetch_reels_v2", return_value=([], False, None)), \
         patch("api_routes.homepage_api.fetch_live_rooms_v2", return_value=([], False, None)), \
         patch("api_routes.homepage_api.fetch_suggested_people_v2", return_value=([], False)), \
         patch("api_routes.homepage_api._fetch_friend_activity", return_value=[]), \
         patch("api_routes.homepage_api.as_completed", side_effect=TimeoutError()), \
         patch("api_routes.homepage_api.rank_homepage_sections", side_effect=lambda payload, **kwargs: payload), \
         patch("api_routes.homepage_api.get_full", return_value=None), \
         patch("api_routes.homepage_api.get_payload", return_value=None):
        payload = app_module.app.test_request_context("/")
        with payload:
            result = app_module.app.view_functions["home"]()
            assert result.status_code == 200

    with patch.object(warmup_module, "homepage_cache_info", return_value={"homepage_cached": False, "homepage_age_seconds": None, "cache_backend": {"backend": "memory", "redis_connected": False, "fallback": True, "latency_ms": 0}}), \
         patch.object(warmup_module, "mark_homepage_cached", side_effect=AssertionError("empty refresh should not mark cache")), \
         patch.object(warmup_module, "set_full", side_effect=AssertionError("empty refresh should not write cache")), \
         patch.object(warmup_module, "set_cache", side_effect=AssertionError("empty refresh should not write cache")), \
         patch.object(warmup_module, "cache_key", side_effect=lambda *parts: "diag:" + "::".join(str(p) for p in parts)), \
         patch("api_routes.homepage_api._build_homepage_contract", return_value={"feed_items": [], "posts": [], "reels": [], "stories": [], "live_rooms": []}):
        result = warmup_module.warm_homepage_cache()
        assert result["ok"] is False
        assert "no public content" in result["error"]

    with patch.object(warmup_module, "homepage_cache_info", return_value={"homepage_cached": True, "homepage_age_seconds": 5, "cache_backend": {"backend": "memory", "redis_connected": False, "fallback": True, "latency_ms": 0}}), \
         patch.object(warmup_module, "mark_homepage_cached") as mark_mock, \
         patch.object(warmup_module, "set_full") as set_full_mock, \
         patch.object(warmup_module, "set_cache") as set_cache_mock:
        result = warmup_module.warm_homepage_cache()
        assert result["ok"] is True
        assert result.get("skipped") is True
        assert mark_mock.call_count == 1
        assert set_full_mock.call_count == 0
        assert set_cache_mock.call_count == 0

    print("TEST_OK homepage warmup/request coordination")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
