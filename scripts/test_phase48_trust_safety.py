#!/usr/bin/env python3
"""
Phase 48 E2E: Trust, Safety, Rule-Based Moderation, Anti-Spam, Wallet Fraud
Uses fake/local mode and does not touch real Neon.
"""
import os, sys, re, uuid

os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_TEST_FAKE_DB"] = "1"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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


PID_A = "phase48-user-a"
PID_B = "phase48-user-b"
ADMIN = "phase48-admin"

print("\n=== 1. MIGRATION ===")
mig = "sql/phase48_trust_safety_moderation.sql"
check("migration exists", os.path.isfile(mig))
sql = open(mig).read() if os.path.isfile(mig) else ""
for table in [
    "chain_trust_scores", "chain_user_reports", "chain_moderation_queue",
    "chain_moderation_actions", "chain_spam_events", "chain_fraud_events",
    "chain_creator_verification_requests", "chain_rate_limit_events",
]:
    check(f"migration creates {table}", table in sql)
check("migration has idempotent indexes", "CREATE INDEX IF NOT EXISTS" in sql)

print("\n=== 2. TRUST SCORE ===")
from services.trust_score_service import (
    get_or_create_trust_score, increase_risk_score, decrease_trust_score,
    increase_trust_score, record_warning, record_restriction,
    recalculate_trust_score, get_trust_summary,
)
trust = get_or_create_trust_score(PID_A)
check("trust score created", trust and trust["trust_score"] == 70)
check("risk score update", increase_risk_score(PID_A, 20)["risk_score"] == 20)
check("trust score bounded low", decrease_trust_score(PID_A, 500)["trust_score"] == 0)
check("trust score bounded high", increase_trust_score(PID_A, 500)["trust_score"] == 100)
check("warning recorded", record_warning(PID_A)["warning_count"] >= 1)
check("restriction recorded", record_restriction(PID_A)["restriction_count"] >= 1)
check("recalculate returns score", "trust_score" in recalculate_trust_score(PID_A))
check("trust summary", get_trust_summary(PID_A).get("ok") is True)

print("\n=== 3. SPAM DETECTION ===")
from services.spam_detection_service import (
    analyze_text_for_spam, check_repeated_content, check_link_risk,
    is_spammy_message, record_spam_event, get_spam_summary,
)
spam = analyze_text_for_spam("Guaranteed profit! click this link https://a.test https://b.test send money")
check("spam text detection", spam["spam"] and spam["score"] >= 50)
check("link risk detection", check_link_risk("visit https://example.test").get("risky") is True)
check("repeated first content ok", check_repeated_content(PID_A, "same message").get("repeated") is False)
check("repeated message detection", check_repeated_content(PID_A, "same message").get("repeated") is False)
check("repeated message escalates", check_repeated_content(PID_A, "same message").get("repeated") is True)
msg_spam = is_spammy_message(PID_A, "crypto airdrop guaranteed profit click this link https://x.test")
check("is_spammy_message flags", msg_spam.get("spam") is True)
check("spam event recorded", record_spam_event(PID_A, "test_spam", 60).get("ok") is True)
check("spam summary", get_spam_summary(PID_A)["count"] >= 1)

print("\n=== 4. FRAUD DETECTION ===")
from services.fraud_detection_service import (
    analyze_wallet_transaction, analyze_tip, analyze_gift, analyze_subscription,
    analyze_payout_request, record_fraud_event, get_fraud_summary,
    is_high_risk_wallet_action,
)
fraud_tx = analyze_wallet_transaction(PID_A, 1000, PID_A)
check("fraud transaction detection", fraud_tx["fraud"] and fraud_tx["severity"] == "critical")
check("tip analysis", analyze_tip(PID_A, PID_B, 25000).get("ok") is True)
check("gift analysis", analyze_gift(PID_A, PID_B, 1000).get("ok") is True)
check("subscription analysis", analyze_subscription(PID_A, PID_B, 1000).get("ok") is True)
payout_fraud = analyze_payout_request(PID_A, 100000, available_balance_cents=0)
check("high-risk payout detection", payout_fraud["fraud"])
check("high-risk wallet helper", is_high_risk_wallet_action(payout_fraud) is True)
check("fraud event recorded", record_fraud_event(PID_A, "test_fraud", 90, "critical").get("ok") is True)
check("fraud summary", get_fraud_summary(PID_A)["count"] >= 1)

print("\n=== 5. MODERATION ===")
from services.moderation_service import (
    create_report, get_reports, resolve_report, add_to_moderation_queue,
    get_moderation_queue, assign_moderation_item, review_moderation_item,
    take_moderation_action, restrict_user, unrestrict_user, warn_user,
    remove_content, restore_content,
)
report = create_report(PID_A, PID_B, "profile", None, "spam", "Spam account")
rid = report["report"]["id"]
check("report creation", report.get("ok") is True)
check("reports listed", len(get_reports(profile_id=PID_A)) >= 1)
check("report resolution", resolve_report(rid, ADMIN).get("ok") is True)
queue_item = add_to_moderation_queue(PID_B, "message", str(uuid.uuid4()), "spam", "high", "test")
qid = queue_item["item"]["id"]
check("moderation queue creation", queue_item.get("ok") is True)
check("moderation queue listed", len(get_moderation_queue()) >= 1)
check("assign moderation item", assign_moderation_item(qid, ADMIN).get("ok") is True)
check("review moderation item", review_moderation_item(qid, ADMIN).get("ok") is True)
check("moderation action warning", take_moderation_action("warn", PID_B, ADMIN).get("ok") is True)
check("warn user", warn_user(PID_B, "test").get("ok") is True)
check("user restriction", restrict_user(PID_B, "test").get("restricted") is True)
check("user unrestriction", unrestrict_user(PID_B).get("restricted") is False)
check("remove content", remove_content("message", str(uuid.uuid4())).get("removed") is True)
check("restore content", restore_content("message", str(uuid.uuid4())).get("restored") is True)

print("\n=== 6. CREATOR VERIFICATION ===")
from services.creator_verification_service import (
    submit_verification_request, get_creator_verification_status,
    approve_creator_verification, reject_creator_verification,
    list_verification_requests,
)
req = submit_verification_request(PID_A, {"category": "music"})
check("creator verification request", req.get("ok") is True)
check("creator verification status pending", get_creator_verification_status(PID_A)["status"] == "pending")
check("creator verification approval", approve_creator_verification(req["request"]["id"], ADMIN).get("ok") is True)
req2 = submit_verification_request(PID_B, {"category": "video"})
check("creator verification rejection", reject_creator_verification(req2["request"]["id"], ADMIN, "Not enough data").get("ok") is True)
check("list verification requests", isinstance(list_verification_requests(), list))

print("\n=== 7. RATE LIMIT ===")
from services.safety_rate_limit_service import record_rate_limit_event, check_action_rate_limit, is_action_blocked, get_rate_limit_summary
check("rate limit event", record_rate_limit_event(PID_A, "report").get("ok") is True)
for _ in range(6):
    rl = check_action_rate_limit(PID_A, "report", limit=3)
check("action block after limit", rl.get("blocked") is True)
check("is_action_blocked", is_action_blocked(PID_A, "report") is True)
check("rate limit summary", get_rate_limit_summary(PID_A)["count"] >= 1)

print("\n=== 8. ROUTES ===")
rules = {r.rule for r in app.url_map.iter_rules()}
for route in [
    "/safety/api/report", "/safety/api/my-reports", "/safety/api/trust-summary",
    "/safety/api/creator-verification/request", "/safety/api/creator-verification/status",
    "/admin/safety/api/reports", "/admin/safety/api/moderation-queue",
    "/admin/safety/api/fraud-events", "/admin/safety/api/spam-events",
    "/admin/safety/api/trust-scores", "/admin/safety/api/creator-verification",
]:
    check(f"route exists {route}", route in rules)

with app.test_client() as c:
    with c.session_transaction() as sess:
        sess["profile_id"] = "phase48-api-user"
        sess["auth_user_id"] = "phase48-api-user"
    check("trust summary API 200", c.get("/safety/api/trust-summary").status_code == 200)
    check("report API 200", c.post("/safety/api/report", json={"reported_profile_id": PID_B, "reason": "spam"}).status_code == 200)
    check("verification status API 200", c.get("/safety/api/creator-verification/status").status_code == 200)

print("\n=== 9. SOCKETS, TEMPLATES, INTEGRATIONS ===")
socket_src = open("services/socket_events.py").read()
for event in [
    "safety:report-created", "safety:warning-issued", "safety:user-restricted",
    "safety:user-unrestricted", "safety:moderation-updated", "safety:fraud-alert",
    "safety:spam-alert", "safety:verification-updated", "trust:score-updated",
]:
    check(f"socket event {event}", event in socket_src)

for tpl in [
    "templates/safety/trust_summary.html", "templates/safety/report.html",
    "templates/safety/creator_verification.html", "templates/admin/safety_dashboard.html",
    "templates/admin/moderation_queue.html", "templates/admin/fraud_events.html",
    "templates/admin/spam_events.html", "templates/admin/creator_verification.html",
]:
    check(f"template exists {tpl}", os.path.isfile(tpl))

check("wallet fraud integration exists", "analyze_tip" in open("services/creator_monetization_service.py").read())
check("payout fraud integration exists", "analyze_payout_request" in open("services/payout_service.py").read())
check("message spam integration exists", "is_spammy_message" in open("services/message_delivery_service.py").read())
check("notification integration exists", "queue_push_event" in open("services/moderation_service.py").read() and "queue_push_event" in open("services/creator_verification_service.py").read())
check("settings UI updated", "Trust Summary" in open("templates/profile/settings.html").read())
check("thread report UI updated", "Report Message" in open("templates/messages/thread.html").read())
check("wallet UI updated", "Creator Verification" in open("templates/wallet/dashboard.html").read())

print("\n=== 10. BACKWARD PHASE FILES ===")
check("Phase 47 test file exists", os.path.isfile("scripts/test_phase47_creator_wallet.py"))
check("Phase 46 test file exists", os.path.isfile("scripts/test_phase46_e2ee_activation.py"))

total = PASS + FAIL
print(f"\n=== PHASE 48 SUMMARY ===")
print(f"  PASS: {PASS}/{total}  FAIL: {FAIL}/{total}")
if FAIL:
    sys.exit(1)
print("  All Phase 48 trust and safety tests passed!")
sys.exit(0)
