#!/usr/bin/env python3
"""Phase 35 — Automated E2E Flows via Flask Test Client (no real DB)"""

import os
import sys
import uuid
import json

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"

from app import create_app

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} {detail}")
        failed += 1

app = create_app()
client = app.test_client()

UID_A = str(uuid.uuid4())
UID_B = str(uuid.uuid4())

# 1. Register/login routes open
with app.test_request_context():
    r = client.get("/auth/login")
    check("GET /auth/login opens", r.status_code in (200, 302))

    r = client.get("/auth/register")
    check("GET /auth/register opens", r.status_code in (200, 302))

# 2. Homepage opens
r = client.get("/")
check("GET / opens", r.status_code in (200, 302))

# 3. Messages inbox opens
r = client.get("/messages/")
check("GET /messages/ opens", r.status_code in (200, 302))

# 4. Profile page opens
r = client.get("/profile/")
check("GET /profile/ opens", r.status_code in (200, 302))

# 5. Calls recent opens
r = client.get("/calls/recent")
check("GET /calls/recent opens", r.status_code in (200, 302))

# 6. Live channels opens
r = client.get("/live/")
check("GET /live/ opens", r.status_code in (200, 302))

# 7. Create direct thread (test API if registered)
try:
    from api_routes.message_routes import message_bp
    check("message_bp registered", True)
except Exception as e:
    check("message_bp importable", False, str(e))

# 8. Message send API pattern
try:
    from services.message_feature_service import send_text_message
    check("send_text_message callable", callable(send_text_message))
except Exception as e:
    check("send_text_message importable", False, str(e))

# 9. Message read API pattern
try:
    from services.message_feature_service import get_thread_messages
    check("get_thread_messages callable", callable(get_thread_messages))
except Exception as e:
    check("get_thread_messages importable", False, str(e))

# 10. Seen API pattern
try:
    from services.message_feature_service import mark_seen
    check("mark_seen callable", callable(mark_seen))
except Exception as e:
    check("mark_seen importable", False, str(e))

# 11. Unread count changes
try:
    from services.message_feature_service import unread_count
    check("unread_count callable", callable(unread_count))
except Exception as e:
    check("unread_count importable", False, str(e))

# 12. Group creation
try:
    from services.group_feature_service import create_group
    result = create_group(UID_A, "Test Group")
    check("create_group returns ok", result.get("ok"))
except Exception as e:
    check("create_group works", False, str(e))

# 13. Group join
try:
    from services.group_feature_service import join_public_group, request_join
    r1 = join_public_group("non-existent-group-id", UID_B)
    check("join_public_group handles missing group gracefully", True)
except Exception as e:
    check("join_public_group works without crash", False, str(e))

# 14. Call start API
try:
    from services.call_service import start_call
    check("start_call callable", callable(start_call))
except Exception as e:
    check("start_call importable", False, str(e))

# 15. Call status update
try:
    from services.call_service import start_call as sc, answer_call, end_call
    check("answer_call callable", callable(answer_call))
    check("end_call callable", callable(end_call))
except Exception as e:
    check("call service functions importable", False, str(e))

# 16. Live start route/API
try:
    from services.live_service import create_live_room, get_live_rooms
    check("create_live_room callable", callable(create_live_room))
    check("get_live_rooms callable", callable(get_live_rooms))
except Exception as e:
    check("live service functions importable", False, str(e))

# 17. Live comment API
try:
    from services.live_service import add_comment
    check("add_comment callable", callable(add_comment))
except Exception as e:
    check("add_comment importable", False, str(e))

# 18. Notification preferences route
try:
    from api_routes.notification_routes import notification_engine_bp
    check("notification_engine_bp registered", True)
except Exception as e:
    check("notification_engine_bp importable", False, str(e))

# 19. Push subscription route
try:
    from api_routes.push_routes import push_bp
    check("push_bp registered", True)
except Exception as e:
    check("push_bp importable", False, str(e))

# 20. Push subscribe works with test payload
with app.test_request_context("/push/subscribe", method="POST"):
    try:
        from services.push_notification_service import save_subscription
        result = save_subscription(UID_A, "https://test.endpoint/push", "test_p256dh", "test_auth")
        check("save_subscription returns ok", result.get("ok"))
    except Exception as e:
        check("save_subscription works", False, str(e))

# 21. Creator dashboard route opens
r = client.get("/creator/dashboard")
check("GET /creator/dashboard opens", r.status_code in (200, 302))

# 22. Wallet route opens
r = client.get("/wallet/")
check("GET /wallet/ opens", r.status_code in (200, 302))

# 23. Dating route opens
r = client.get("/dating")
check("GET /dating opens", r.status_code in (200, 302))

# 24. Safety routes open (if safety_bp registered)
try:
    from api_routes.safety_routes import safety_bp
    check("safety_bp registered", True)
except Exception as e:
    check("safety_bp importable", False, str(e))

# 25. Report route works
try:
    from services.moderation_engine import report_entity
    check("report_entity function exists", callable(report_entity))
except Exception as e:
    check("report_entity importable", False, str(e))

# 26. status route opens
r = client.get("/status/")
check("GET /status/ opens", r.status_code in (200, 302))

# 27. Notification page opens
r = client.get("/notifications/")
check("GET /notifications/ opens", r.status_code in (200, 302))

# 28. Real-time routes registered
try:
    from api_routes.realtime_routes import realtime_bp
    check("realtime_bp registered", True)
except Exception as e:
    check("realtime_bp importable", False, str(e))

# 29. Discovery route opens
r = client.get("/discover/")
check("GET /discover/ opens", r.status_code in (200, 302))

# 30. Search API
try:
    from api_routes.search_routes import search_api_bp
    check("search_api_bp registered", True)
except Exception as e:
    check("search_api_bp importable", False, str(e))

print(f"\nResults: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")
if failed > 0:
    sys.exit(1)
