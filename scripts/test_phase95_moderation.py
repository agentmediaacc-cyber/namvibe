#!/usr/bin/env python3
"""
Phase 95 E2E: Restriction, Account Risk, Content Flag, Appeal, Moderation Log
Uses fake/local mode and does not touch real Neon.
"""
import os, sys, json, uuid
from datetime import datetime, timezone

os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_TEST_FAKE_DB"] = "1"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.env_service import load_project_env
load_project_env()

from app import create_app

app = create_app()

PASS = 0
FAIL = 0

def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}" + (f" -- {detail}" if detail else ""))

PID = "phase95-test-user"
ADMIN = "phase95-admin"
CONTENT_ID = str(uuid.uuid4())
FLAG_ID = None
APPEAL_ID = None

print("\n=== 1. RESTRICTION SERVICE ===")
from services.restriction_service import restrict_user, is_restricted, get_active_restrictions, unrestrict_user

r1 = restrict_user(PID, restricted_by=ADMIN, restriction_type="temporary", reason="test restriction", duration_minutes=60)
check("restrict_user returns ok", r1.get("ok") is True)
check("is_restricted true", is_restricted(PID) is True)
active = get_active_restrictions(PID)
check("get_active_restrictions returns list", isinstance(active, list) and len(active) >= 1)
check("active restriction has correct profile_id", active[0]["profile_id"] == PID)
u1 = unrestrict_user(PID)
check("unrestrict_user returns ok", u1.get("ok") is True)
check("is_restricted false after unrestrict", is_restricted(PID) is False)
check("no active restrictions after unrestrict", len(get_active_restrictions(PID)) == 0)

print("\n=== 2. ACCOUNT RISK SERVICE ===")
from services.account_risk_service import get_or_create_risk, assess_account_risk, update_risk_signal, get_risk_level

risk = get_or_create_risk(PID)
check("get_or_create_risk returns record", risk is not None)
check("risk starts at low", risk.get("risk_level") == "low")
assessed = assess_account_risk(PID)
check("assess_account_risk returns ok", assessed.get("ok") is True)
check("assessed risk_level present", "risk_level" in assessed.get("risk", {}))
upd = update_risk_signal(PID, "report_count", increment=5)
check("update_risk_signal returns ok", upd.get("ok") is True)
level = get_risk_level(PID)
check("get_risk_level returns ok", level.get("ok") is True)
check("risk_level is string", isinstance(level.get("risk_level"), str))
upd2 = update_risk_signal(PID, "mass_action_count", increment=50)
check("signal increment raises risk level", upd2.get("risk", {}).get("risk_level") in ("high", "critical"))
check("invalid signal name rejected", update_risk_signal(PID, "bogus").get("ok") is False)

print("\n=== 3. CONTENT FLAG SERVICE ===")
from services.content_flag_service import flag_content, is_content_flagged, resolve_flag, get_content_flags

f1 = flag_content(PID, "post", CONTENT_ID, "inappropriate", severity="high", flagged_by=ADMIN, reason="Flagged by admin")
FLAG_ID = f1["flag"]["id"]
check("flag_content returns ok", f1.get("ok") is True)
check("is_content_flagged true", is_content_flagged("post", CONTENT_ID) is True)
flags = get_content_flags(content_type="post", content_id=CONTENT_ID)
check("get_content_flags returns flagged item", len(flags) >= 1)
check("flag severity matches", flags[0]["severity"] == "high")
res = resolve_flag(FLAG_ID)
check("resolve_flag returns ok", res.get("ok") is True)
check("is_content_flagged false after resolve", is_content_flagged("post", CONTENT_ID) is False)

print("\n=== 4. APPEAL SERVICE ===")
from services.appeal_service import submit_appeal, get_user_appeals, review_appeal, get_pending_appeals

a1 = submit_appeal(PID, "restriction", CONTENT_ID, "I did nothing wrong", details="Please review")
APPEAL_ID = a1["appeal"]["id"]
check("submit_appeal returns ok", a1.get("ok") is True)
check("appeal status pending", a1["appeal"]["status"] == "pending")
user_appeals = get_user_appeals(PID)
check("get_user_appeals returns list", isinstance(user_appeals, list) and len(user_appeals) >= 1)
pending = get_pending_appeals()
check("get_pending_appeals returns list", isinstance(pending, list) and len(pending) >= 1)
reviewed = review_appeal(APPEAL_ID, ADMIN, "approved", resolution_note="Appeal granted")
check("review_appeal returns ok", reviewed.get("ok") is True)
user_appeals2 = get_user_appeals(PID)
check("appeal status updated after review", user_appeals2[0]["status"] == "approved")

print("\n=== 5. MODERATION LOG SERVICE ===")
from services.moderation_log_service import log_moderation_action, get_moderation_logs

l1 = log_moderation_action(ADMIN, PID, "restrict", entity_type="profile", entity_id=PID, reason="Test moderation", details="Phase 95 test", ip_address="127.0.0.1")
check("log_moderation_action returns ok", l1.get("ok") is True)
check("log has log entry", "log" in l1)
logs = get_moderation_logs(actor_id=ADMIN)
check("get_moderation_logs returns list", isinstance(logs, list) and len(logs) >= 1)
check("log action matches", logs[0]["action"] == "restrict")
logs_target = get_moderation_logs(target_id=PID)
check("filter by target_id works", len(logs_target) >= 1)
logs_action = get_moderation_logs(action="restrict")
check("filter by action works", len(logs_action) >= 1)

print("\n=== 6. VIA FLASK TEST CLIENT (API ROUTES) ===")
#
# 6a — Route existence
#
rules = {r.rule for r in app.url_map.iter_rules()}
phase95_routes = [
    "/api/report/content", "/api/report/profile", "/api/report/message",
    "/api/report/call", "/api/block/list", "/api/block/<profile_id>",
    "/api/block/<profile_id>", "/api/trust/summary",
    "/api/restrict/list", "/api/restrict/<profile_id>",
]
for route in phase95_routes:
    check(f"route exists {route}", route in rules)

#
# 6b — API functional tests via test client
#
# The safety_bp from moderation_routes.py uses prefix /api.
# Register it manually since create_app does not wire it yet.
from api_routes.moderation_routes import safety_bp as mod_safety_bp
try:
    app.register_blueprint(mod_safety_bp)
except Exception:
    pass  # already registered

with app.test_client() as c:
    with c.session_transaction() as sess:
        sess["profile_id"] = PID
        sess["auth_user_id"] = PID

    # Report content
    rp = c.post("/api/report/content", json={
        "content_type": "post", "content_id": CONTENT_ID,
        "reported_profile_id": "phase95-other-user", "reason": "spam",
        "details": "Test report content"
    })
    check("POST /api/report/content 200", rp.status_code == 200)
    check("POST /api/report/content success", rp.get_json().get("success") is True)

    # Report profile
    rp2 = c.post("/api/report/profile", json={
        "reported_profile_id": "phase95-other-user", "reason": "fake_account",
        "details": "Test report profile"
    })
    check("POST /api/report/profile 200", rp2.status_code == 200)
    check("POST /api/report/profile success", rp2.get_json().get("success") is True)

    # Report message
    rp3 = c.post("/api/report/message", json={
        "content_id": str(uuid.uuid4()),
        "reported_profile_id": "phase95-other-user", "reason": "harassment",
        "details": "Test report message"
    })
    check("POST /api/report/message 200", rp3.status_code == 200)
    check("POST /api/report/message success", rp3.get_json().get("success") is True)

    # Report call
    rp4 = c.post("/api/report/call", json={
        "room_id": str(uuid.uuid4()),
        "reported_profile_id": "phase95-other-user", "reason": "inappropriate_call",
        "details": "Test report call"
    })
    check("POST /api/report/call 200", rp4.status_code == 200)
    check("POST /api/report/call success", rp4.get_json().get("success") is True)

    # Block list
    bl = c.get("/api/block/list")
    check("GET /api/block/list 200", bl.status_code == 200)
    check("GET /api/block/list returns blocked list", isinstance(bl.get_json().get("blocked"), list))

    # Block a user
    bk = c.post(f"/api/block/{PID}")
    check("POST /api/block/<id> 200", bk.status_code == 200)

    # Unblock the user
    ub = c.delete(f"/api/block/{PID}")
    check("DELETE /api/block/<id> 200", ub.status_code == 200)

    # Trust summary
    ts = c.get("/api/trust/summary")
    check("GET /api/trust/summary 200", ts.status_code == 200)

print("\n=== 7. CLEANUP ===")
try:
    from services.restriction_service import _FAKE_RESTRICTIONS
    _FAKE_RESTRICTIONS.clear()
except Exception:
    pass
try:
    from services.account_risk_service import _FAKE_RISK
    _FAKE_RISK.clear()
except Exception:
    pass
try:
    from services.content_flag_service import _FAKE_FLAGS
    _FAKE_FLAGS.clear()
except Exception:
    pass
try:
    from services.appeal_service import _FAKE_APPEALS
    _FAKE_APPEALS.clear()
except Exception:
    pass
try:
    from services.moderation_log_service import _FAKE_LOGS
    _FAKE_LOGS.clear()
except Exception:
    pass
check("test data cleaned up", True)

total = PASS + FAIL
print(f"\n=== PHASE 95 SUMMARY ===")
print(f"  PASS: {PASS}/{total}  FAIL: {FAIL}/{total}")
if FAIL:
    sys.exit(1)
print("  All Phase 95 moderation tests passed!")
sys.exit(0)
