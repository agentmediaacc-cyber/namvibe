#!/usr/bin/env python3
"""Phase 36 — Live Streaming Infrastructure Check"""

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

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

# 1. Service loads
try:
    from services.media_server_service import (
        is_live_streaming_ready, get_media_server_url,
        get_rtmp_ingest_url, get_livekit_config,
    )
    check("media_server_service loads", True)
except Exception as e:
    check("media_server_service loads", False, str(e))
    sys.exit(1)

# 2. Status detection
status = is_live_streaming_ready()
check("is_live_streaming_ready returns dict", isinstance(status, dict))
check("status has 'status' key", "status" in status)
check("status has 'backends' key", "backends" in status)
check("status has 'capabilities' key", "capabilities" in status)

# 3. Backend detection
backends = status.get("backends", [])
env_rtmp = os.environ.get("RTMP_SERVER_URL", "")
env_media = os.environ.get("MEDIA_SERVER_URL", "")
env_livekit = os.environ.get("LIVEKIT_URL", "")

# Detection should match env presence
if env_rtmp and "rtmp" not in backends:
    check("RTMP backend detected", False, "RTMP_SERVER_URL set but not detected")
elif not env_rtmp:
    check("RTMP not configured (expected)", True)

if env_livekit and "livekit" not in backends:
    check("LiveKit backend detected", False, "LIVEKIT_URL set but not detected")
elif not env_livekit:
    check("LiveKit not configured (expected)", True)

# 4. Capability flags
caps = status.get("capabilities", {})
check("broadcast capability defined", "broadcast" in caps)
check("webrtc_broadcast capability defined", "webrtc_broadcast" in caps)
check("rtmp_ingest capability defined", "rtmp_ingest" in caps)
check("recording capability defined", "recording" in caps)

# 5. Status classification
s = status.get("status")
check("status is valid classification", s in ("ready", "partial", "missing"))
print(f"  [INFO] Live streaming status: {s}")
print(f"  [INFO] Backends detected: {backends}")
print(f"  [INFO] Active capabilities: {status.get('active_capabilities')}/{status.get('total_capabilities')}")

# 6. Helper functions
url = get_media_server_url()
check("get_media_server_url returns string or None", url is None or isinstance(url, str))

rtmp = get_rtmp_ingest_url()
check("get_rtmp_ingest_url works", rtmp is None or rtmp.startswith("rtmp://"))

lk = get_livekit_config()
if env_livekit:
    check("get_livekit_config returns config", lk is not None)
    check("livekit config has url", lk.get("url") == env_livekit)
else:
    check("get_livekit_config returns None (expected)", lk is None)

# 7. RTMP detection
if not env_rtmp and not env_media and not env_livekit:
    print()
    print("  [INFRASTRUCTURE REQUIRED]")
    print("    No media server configured. Set RTMP_SERVER_URL, MEDIA_SERVER_URL, or LIVEKIT_URL.")
    print("    Recommended: LiveKit for production WebRTC + RTMP hybrid.")

print(f"\nResults: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")
if failed > 0:
    sys.exit(1)
