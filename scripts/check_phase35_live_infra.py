#!/usr/bin/env python3
"""Phase 35 — Live Streaming Infrastructure Check"""

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

passed = 0
failed = 0
partial = 0
infra_required = []

STATUS = {"ready": [], "partial": [], "missing": [], "infrastructure_required": []}

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
        STATUS["ready"].append(name)
    else:
        print(f"  [FAIL] {name} {detail}")
        failed += 1
        if "required" in detail.lower():
            STATUS["infrastructure_required"].append(name)
        else:
            STATUS["missing"].append(name)

def partial_check(name, detail=""):
    global partial
    print(f"  [PARTIAL] {name} {detail}")
    partial += 1
    STATUS["partial"].append(name)

# 1. Live routes exist
routes_dir = os.path.join(BASE, "api_routes")
live_routes = os.path.join(routes_dir, "live_routes.py")
live_media = os.path.join(routes_dir, "live_media_routes.py")
check("Live routes file exists", os.path.exists(live_routes), "live_routes.py not found")
check("Live media routes file exists", os.path.exists(live_media), "live_media_routes.py not found")

# 2. Live services exist
svc_dir = os.path.join(BASE, "services")
check("Live service exists", os.path.exists(os.path.join(svc_dir, "live_service.py")))
check("Live feature service exists", os.path.exists(os.path.join(svc_dir, "live_feature_service.py")))
check("Live media service exists", os.path.exists(os.path.join(svc_dir, "live_media_service.py")))

# 3. Live templates exist
tpl_dir = os.path.join(BASE, "templates", "live")
templates = ["channels.html", "studio.html", "watch.html", "room.html", "home.html", "locked.html"]
for t in templates:
    check(f"Live template {t} exists", os.path.exists(os.path.join(tpl_dir, t)), f"{t} not found")

# 4. WebRTC broadcast hook
webrtc_hook = False
js_dir = os.path.join(BASE, "static", "js")
if os.path.isdir(js_dir):
    for f in os.listdir(js_dir):
        if f.endswith(".js"):
            fp = os.path.join(js_dir, f)
            try:
                content = open(fp).read()
                if "webrtc" in content.lower() or "getUserMedia" in content or "RTCPeerConnection" in content:
                    webrtc_hook = True
            except Exception:
                pass
check("WebRTC broadcast hook in JS", webrtc_hook, "No WebRTC broadcast references in JS")

# 5. RTMP server env
rtmp_env = os.environ.get("RTMP_SERVER") or os.environ.get("MEDIA_SERVER") or ""
check("RTMP server env configured", bool(rtmp_env), "RTMP/media server required for TikTok-style production live streaming")

# 6. Media server env
media_server = os.environ.get("MEDIA_SERVER") or os.environ.get("STREAM_SERVER") or ""
check("Media server env configured", bool(media_server), "Media server env not set")

# 7. Replay storage
replay_storage = False
try:
    from services.live_feature_service import save_replay
    replay_storage = callable(save_replay)
except Exception:
    pass
check("Replay storage function exists", replay_storage, "save_replay not found")

# 8. Clip storage
clip_storage = False
try:
    from services.live_feature_service import create_clip
    clip_storage = callable(create_clip)
except Exception:
    pass
check("Clip storage function exists", clip_storage, "create_clip not found")

# 9. Live viewer count
viewer_count = False
try:
    from services.live_service import get_live_rooms
    viewer_count = callable(get_live_rooms)
except Exception:
    pass
check("Live viewer count (get_live_rooms)", viewer_count)

# 10. Live comments
comments = False
try:
    from services.live_service import add_comment
    comments = callable(add_comment)
except Exception:
    pass
check("Live comments (add_comment)", comments)

# 11. Live gifts
gifts = False
try:
    from services.live_service import send_gift
    gifts = callable(send_gift)
except Exception:
    pass
check("Live gifts (send_gift)", gifts)

# 12. Live moderation
moderation = False
try:
    from services.live_service import add_moderator
    moderation = callable(add_moderator)
except Exception:
    pass
check("Live moderation (add_moderator)", moderation)

# 13. Live DB tables
sql_dir = os.path.join(BASE, "sql")
tables_found = 0
expected_tables = [
    "chain_live_rooms", "chain_live_viewers", "chain_live_comments",
    "chain_live_gifts", "chain_live_polls", "chain_live_battles",
    "chain_live_replays", "chain_live_clips", "chain_live_stream_settings",
]
if os.path.isdir(sql_dir):
    sql_content = ""
    for root, dirs, files in os.walk(sql_dir):
        for f in files:
            if f.endswith(".sql"):
                sql_content += open(os.path.join(root, f)).read()
    for tbl in expected_tables:
        if tbl in sql_content:
            tables_found += 1
check(f"Live DB tables ({tables_found}/{len(expected_tables)})", tables_found >= 9, f"Only {tables_found}/{len(expected_tables)} live tables found in SQL")

# 14. Socket events for live
try:
    socket_src = open(os.path.join(BASE, "services", "socket_events.py")).read()
    events = ["join_live_room", "leave_live_room", "live_chat_message", "live_gift"]
    for evt in events:
        check(f"Socket event '{evt}' registered", evt in socket_src)
except Exception as e:
    check("Live socket events readable", False, str(e))

print()
print("  [SUMMARY] Live Streaming Infrastructure:")
print(f"    Ready: {len(STATUS['ready'])}")
print(f"    Partial: {len(STATUS['partial'])}")
print(f"    Missing: {len(STATUS['missing'])}")
print(f"    Infrastructure required: {len(STATUS['infrastructure_required'])}")
if not rtmp_env:
    print()
    print("  [INFRASTRUCTURE REQUIRED]")
    print("    RTMP/media server required for TikTok-style production live streaming.")
    print("    Set RTMP_SERVER or MEDIA_SERVER environment variable.")
print()
print(f"Results: {passed}/{passed+failed+partial} passed, {failed}/{passed+failed+partial} failed, {partial}/{passed+failed+partial} partial")
if failed > 0:
    sys.exit(1)
