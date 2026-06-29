#!/usr/bin/env python3
"""Phase 6 — Live Streaming + Gifts Tests (20 tests)"""

import json
import os
import sys
import traceback
from unittest.mock import patch, MagicMock, PropertyMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0
ERRORS = []


def test(label, fn):
    global PASS, FAIL
    try:
        fn()
        PASS += 1
        print(f"  ✅ {label}")
    except Exception as e:
        FAIL += 1
        msg = f"  ❌ {label} — {e}"
        ERRORS.append(msg)
        print(msg)
        traceback.print_exc()


import importlib.util
spec = importlib.util.spec_from_file_location("live_engine_test", "services/live_engine.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


print("\n═══ Phase 6 — Live Streaming + Gifts Tests ═══\n")

# ─── Room Lifecycle ───

def test_create_room_returns_dict_with_ok():
    with patch.object(mod, "_legacy_create_room", return_value={"id": "r1", "title": "Test"}):
        with patch.object(mod, "_emit_activity"):
            with patch.object(mod, "_notify_followers_live_started"):
                with patch.object(mod, "emit_to_live_room"):
                    result = mod.create_live_room({"title": "Test"})
                    assert isinstance(result, dict), "Expected dict"
                    assert "ok" in result, "Expected ok key"

test("create_live_room returns dict with ok key", test_create_room_returns_dict_with_ok)


def test_create_room_failure_returns_ok_false():
    with patch.object(mod, "_legacy_create_room", return_value=None):
        result = mod.create_live_room({"title": "Test"})
        assert result.get("ok") is False, "Expected ok=False"

test("create_live_room failure returns ok=False", test_create_room_failure_returns_ok_false)


def test_get_room_returns_ok():
    with patch.object(mod, "_legacy_get_room", return_value={"id": "r1"}):
        result = mod.get_live_room("r1")
        assert result.get("ok") is True, f"Expected ok=True, got {result}"
        assert result.get("room") is not None

test("get_live_room returns ok=True for found room", test_get_room_returns_ok)


def test_get_room_not_found():
    with patch.object(mod, "_legacy_get_room", return_value=None):
        result = mod.get_live_room("nonexistent")
        assert result.get("ok") is False
        assert "error" in result

test("get_live_room returns ok=False for missing room", test_get_room_not_found)


def test_list_rooms_returns_list():
    with patch.object(mod, "_legacy_get_rooms", return_value=[{"id": "r1"}, {"id": "r2"}]):
        result = mod.get_live_rooms()
        assert result.get("ok") is True
        assert isinstance(result.get("rooms"), list)

test("get_live_rooms returns rooms list", test_list_rooms_returns_list)


# ─── Moderation ───

def test_moderate_unauthorized():
    with patch.object(mod, "_legacy_get_room", return_value={"id": "r1", "host_profile_id": "host1"}):
        with patch.object(mod, "_can_moderate", return_value=False):
            result = mod.moderate_live_user("r1", "user1", "ban", target_profile_id="target1")
            assert result.get("ok") is False

test("moderate_live_user unauthorized returns ok=False", test_moderate_unauthorized)


def test_moderate_unknown_action():
    with patch.object(mod, "_legacy_get_room", return_value={"id": "r1", "host_profile_id": "host1"}):
        with patch.object(mod, "_can_moderate", return_value=True):
            result = mod.moderate_live_user("r1", "host1", "nonexistent_action", target_profile_id="target1")
            assert result.get("ok") is False
            assert "unknown_action" in result.get("error", "")

test("moderate_live_user unknown action returns error", test_moderate_unknown_action)


# ─── Chat ───

def test_send_chat_empty_body():
    with patch.object(mod, "_ls_is_banned", return_value=False):
        result = mod.send_live_chat("r1", "u1", "   ")
        assert result.get("ok") is False

test("send_live_chat empty body returns ok=False", test_send_chat_empty_body)


def test_send_chat_banned():
    with patch.object(mod, "_ls_is_banned", return_value=True):
        result = mod.send_live_chat("r1", "u1", "hello")
        assert result.get("ok") is False
        assert result.get("error") == "banned"

test("send_live_chat banned user returns error", test_send_chat_banned)


# ─── Reactions ───

def test_send_reaction_returns_ok():
    with patch("services.realtime_service.track_live_reaction"):
        with patch.object(mod, "emit_to_live_room"):
            with patch.object(mod, "_emit_activity"):
                result = mod.send_live_reaction("r1", "u1", "heart")
                assert result.get("ok") is True
                assert result.get("reaction") is not None

test("send_live_reaction returns ok=True", test_send_reaction_returns_ok)


# ─── Gifts ───

def test_send_gift_room_not_found():
    with patch.object(mod, "_legacy_get_room", return_value=None):
        result = mod.send_live_gift("nonexistent", "u1", "Gift", "🎁", 10)
        assert result.get("ok") is False
        assert "room_not_found" in result.get("error", "")

test("send_live_gift missing room returns error", test_send_gift_room_not_found)


def test_send_gift_wallet_disabled():
    with patch.object(mod, "_legacy_get_room", return_value={"id": "r1", "host_profile_id": "host1"}):
        with patch.object(mod, "_deduct_coins_wallet", return_value={"ok": False, "error": "wallet_disabled"}):
            result = mod.send_live_gift("r1", "u1", "Gift", "🎁", 10)
            assert result.get("ok") is False
            assert result.get("code") == "wallet_disabled", f"Expected wallet_disabled, got {result}"

test("send_live_gift wallet_disabled returns correct code", test_send_gift_wallet_disabled)


def test_send_gift_zero_coins_bypasses_wallet():
    with patch.object(mod, "_legacy_get_room", return_value={"id": "r1", "host_profile_id": "host1"}):
        with patch.object(mod, "_legacy_send_gift"):
            with patch.object(mod, "_create_notification"):
                with patch.object(mod, "_emit_activity"):
                    with patch.object(mod, "emit_to_live_room"):
                        result = mod.send_live_gift("r1", "u1", "Free", "❤️", 0)
                        assert result.get("ok") is True

test("send_live_gift zero coins bypasses wallet", test_send_gift_zero_coins_bypasses_wallet)


# ─── Cohosts ───

def test_add_cohost_returns_dict():
    with patch.object(mod, "_ls_promote_cohost", return_value=(True, "Co-host added")):
        with patch.object(mod, "_create_notification"):
            with patch.object(mod, "_emit_activity"):
                result = mod.add_cohost("r1", "u1", "host1")
                assert isinstance(result, dict)
                assert "ok" in result

test("add_cohost returns dict with ok", test_add_cohost_returns_dict)


def test_add_cohost_failure():
    with patch.object(mod, "_ls_promote_cohost", return_value=(False, "Room not found")):
        result = mod.add_cohost("r1", "u1", "host1")
        assert result.get("ok") is False

test("add_cohost failure returns ok=False", test_add_cohost_failure)


# ─── Guest Management ───

def test_approve_guest_returns_ok():
    with patch.object(mod, "_lf_update_guest_request", return_value={"ok": True}):
        result = mod.approve_guest_request("req1")
        assert result.get("ok") is True

test("approve_guest_request returns ok=True", test_approve_guest_returns_ok)


def test_reject_guest_returns_ok():
    with patch.object(mod, "_lf_update_guest_request", return_value={"ok": True}):
        result = mod.reject_guest_request("req1")
        assert result.get("ok") is True

test("reject_guest_request returns ok=True", test_reject_guest_returns_ok)


# ─── Analytics ───

def test_room_analytics_returns_analytics():
    with patch.object(mod, "_legacy_get_room", return_value={"id": "r1", "is_live": True, "created_at": "2026-01-01T00:00:00+00:00"}):
        with patch.object(mod, "_legacy_room_activity", return_value={"viewers": [{"id": "v1"}], "comments": [{"id": "c1"}], "gifts": []}):
            result = mod.get_live_analytics("r1")
            assert result.get("ok") is True, f"Expected ok=True, got {result}"
            assert "analytics" in result
            assert result["analytics"]["viewer_count"] == 1

test("get_live_analytics returns analytics data", test_room_analytics_returns_analytics)


def test_room_analytics_not_found():
    with patch.object(mod, "_legacy_get_room", return_value=None):
        result = mod.get_live_analytics("nonexistent")
        assert result.get("ok") is False

test("get_live_analytics not found returns ok=False", test_room_analytics_not_found)


def test_creator_analytics():
    with patch.object(mod, "safe_select", return_value=[{"is_live": True, "viewer_count": 10, "gift_total": 100}]):
        result = mod.get_creator_live_analytics("creator1")
        assert result.get("ok") is True
        assert result["analytics"]["total_rooms"] == 1
        assert result["analytics"]["live_rooms"] == 1
        assert result["analytics"]["total_viewers"] == 10

test("get_creator_live_analytics returns creator stats", test_creator_analytics)


# ─── Trending ───

def test_trending_rooms():
    with patch.object(mod, "safe_select", return_value=[{"id": "r1", "viewer_count": 100}]):
        result = mod.get_trending_live_rooms()
        assert result.get("ok") is True
        assert isinstance(result.get("rooms"), list)

test("get_trending_live_rooms returns ok=True", test_trending_rooms)


# ─── Gifts ───

def test_gift_leaderboard():
    with patch.object(mod, "get_live_gift_leaderboard", wraps=mod.get_live_gift_leaderboard) as wrapped:
        with patch("services.live_service.get_room_leaderboard", return_value=[{"username": "u1", "total_coins": 100}]):
            result = mod.get_live_gift_leaderboard("r1")
            assert result.get("ok") is True

test("get_live_gift_leaderboard returns ok=True", test_gift_leaderboard)


def test_gift_catalog():
    with patch.object(mod, "_ls_get_gift_catalog", return_value=[{"id": "g1", "gift_name": "Heart"}]):
        result = mod.get_live_gift_catalog()
        assert result.get("ok") is True

test("get_live_gift_catalog returns ok=True", test_gift_catalog)


# ─── is_user_banned ───

def test_is_user_banned():
    with patch.object(mod, "_ls_is_banned", return_value=True):
        result = mod.is_user_banned("r1", "u1")
        assert result.get("ok") is True
        assert result.get("banned") is True

test("is_user_banned returns correct status", test_is_user_banned)


# ─── Summary ───
print(f"\n═══ Results: {PASS} passed, {FAIL} failed ═══\n")
for err in ERRORS:
    print(err)
print(f"\n{PASS}/{PASS + FAIL} tests passed")

if FAIL > 0:
    sys.exit(1)
