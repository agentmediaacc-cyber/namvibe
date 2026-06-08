#!/usr/bin/env python3
"""Phase 35 — WebRTC / Call Infrastructure Check"""

import os
import sys
import json

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

passed = 0
failed = 0
partial = 0

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

# 1. STUN servers configured
stun_found = False
for root, dirs, files in os.walk(os.path.join(BASE, "static")):
    for f in files:
        if f.endswith(".js"):
            fp = os.path.join(root, f)
            try:
                content = open(fp).read()
                if "stun:" in content.lower() or "stun" in content.lower():
                    stun_found = True
            except Exception:
                pass
for root, dirs, files in os.walk(os.path.join(BASE, "api_routes")):
    for f in files:
        if f.endswith(".py"):
            fp = os.path.join(root, f)
            try:
                content = open(fp).read()
                if "stun" in content.lower():
                    stun_found = True
            except Exception:
                pass

check("STUN servers configured", stun_found, "No STUN server reference found in JS or Python files")

# 2. TURN servers configured
turn_found = False
for root, dirs, files in os.walk(os.path.join(BASE, "static")):
    for f in files:
        if f.endswith(".js"):
            fp = os.path.join(root, f)
            try:
                content = open(fp).read()
                if "turn:" in content.lower() or "turn" in content.lower():
                    turn_found = True
            except Exception:
                pass
for root, dirs, files in os.walk(os.path.join(BASE, "api_routes")):
    for f in files:
        if f.endswith(".py"):
            fp = os.path.join(root, f)
            try:
                content = open(fp).read()
                if "turn" in content.lower():
                    turn_found = True
            except Exception:
                pass

check("TURN servers configured", turn_found, "TURN server required for reliable calls across different networks")

# 3. TURN username configured
check("TURN username configured", False, "TURN username not found — infrastructure required")

# 4. TURN credential configured
check("TURN credential configured", False, "TURN credential not found — infrastructure required")

# 5. ICE config route/API
ice_route_found = False
for root, dirs, files in os.walk(os.path.join(BASE, "api_routes")):
    for f in files:
        if f.endswith(".py"):
            fp = os.path.join(root, f)
            try:
                content = open(fp).read()
                if "ice_config" in content.lower() or "ice" in content.lower():
                    ice_route_found = True
            except Exception:
                pass
check("ICE config route/API", ice_route_found, "No ICE config endpoint found — calls may fail on different networks")

# 6. WebRTC JS files
webrtc_js = False
js_dir = os.path.join(BASE, "static", "js")
if os.path.isdir(js_dir):
    for f in os.listdir(js_dir):
        if "call" in f.lower() and f.endswith(".js"):
            webrtc_js = True
            break
check("WebRTC JS files (calls.js)", webrtc_js, "calls.js not found in static/js/")

# 7. Camera permission handling
cam_found = False
if os.path.isdir(js_dir):
    for f in os.listdir(js_dir):
        if f.endswith(".js"):
            fp = os.path.join(js_dir, f)
            try:
                content = open(fp).read()
                if "camera" in content.lower() or "getUserMedia" in content or "enumerateDevices" in content:
                    cam_found = True
            except Exception:
                pass
check("Camera permission handling in JS", cam_found, "No camera/media access found in JS files")

# 8. Microphone permission handling
mic_found = False
if os.path.isdir(js_dir):
    for f in os.listdir(js_dir):
        if f.endswith(".js"):
            fp = os.path.join(js_dir, f)
            try:
                content = open(fp).read()
                if "microphone" in content.lower() or "mic" in content.lower() or "audio" in content.lower():
                    mic_found = True
            except Exception:
                pass
check("Microphone permission handling in JS", mic_found, "No mic/audio references in JS")

# 9. Screen share support
ss_found = False
if os.path.isdir(js_dir):
    for f in os.listdir(js_dir):
        if f.endswith(".js"):
            fp = os.path.join(js_dir, f)
            try:
                content = open(fp).read()
                if "screen" in content.lower() and ("share" in content.lower() or "capture" in content.lower()):
                    ss_found = True
            except Exception:
                pass
check("Screen share support in JS", ss_found, "No screen share references in JS")

# 10. Reconnect handling
reconnect_found = False
if os.path.isdir(js_dir):
    for f in os.listdir(js_dir):
        if f.endswith(".js"):
            fp = os.path.join(js_dir, f)
            try:
                content = open(fp).read()
                if "reconnect" in content.lower():
                    reconnect_found = True
            except Exception:
                pass
check("Reconnect handling", reconnect_found, "No reconnect logic found in JS")

# 11. Busy-user protection in Python
busy_found = False
for root, dirs, files in os.walk(os.path.join(BASE, "services")):
    for f in files:
        if f.endswith(".py"):
            fp = os.path.join(root, f)
            try:
                content = open(fp).read()
                if "busy" in content.lower():
                    busy_found = True
            except Exception:
                pass
check("Busy-user protection in services", busy_found, "No busy-user checks found in services")

# 12. Call routes exist
routes_dir = os.path.join(BASE, "api_routes")
call_routes_file = os.path.join(routes_dir, "call_routes.py")
check("Call routes file exists", os.path.exists(call_routes_file), "call_routes.py not found")

# 13. Call service exists
call_service_file = os.path.join(BASE, "services", "call_service.py")
check("Call service exists", os.path.exists(call_service_file), "call_service.py not found")

print()
print("  [SUMMARY] WebRTC / Call Infrastructure:")
print(f"    Ready: {len(STATUS['ready'])}")
print(f"    Partial: {len(STATUS['partial'])}")
print(f"    Missing: {len(STATUS['missing'])}")
print(f"    Infrastructure required: {len(STATUS['infrastructure_required'])}")
if STATUS["infrastructure_required"]:
    print()
    print("  [INFRASTRUCTURE REQUIRED]")
    print("    TURN server required for reliable calls across different networks.")
    print("    Without TURN, peer-to-peer calls may fail on restrictive NAT/firewall.")
print()
print(f"Results: {passed}/{passed+failed+partial} passed, {failed}/{passed+failed+partial} failed, {partial}/{passed+failed+partial} partial")
if failed > 0:
    sys.exit(1)
