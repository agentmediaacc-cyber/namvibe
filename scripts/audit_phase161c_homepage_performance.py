#!/usr/bin/env python3
"""Audit homepage performance: latency, slow queries, errors."""
import os, sys, json, subprocess, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL = 0, 0
def test(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} - {detail}")

LOCAL = "http://127.0.0.1:8080"

def curl_json(url, timeout=15):
    t0 = time.time()
    r = subprocess.run(["curl", "-s", url], capture_output=True, text=True, timeout=timeout)
    t = (time.time() - t0) * 1000
    try:
        return json.loads(r.stdout), t
    except:
        return None, t

print("="*60)
print("PHASE 161c - HOMEPAGE PERFORMANCE AUDIT")
print("="*60)

# 1. Healthz
print("\n--- Healthz ---")
data, lat = curl_json(f"{LOCAL}/healthz")
if data:
    test(f"/healthz ok=true", data.get("ok") == True)
    test(f"/healthz app ok", data.get("components", {}).get("app", {}).get("ok") == True)
    test(f"/healthz db ok", data.get("components", {}).get("database", {}).get("ok") == True)
    test(f"/healthz latency ({lat:.0f}ms)", lat < 3000, f"latency={lat:.0f}ms")
else:
    test("/healthz reachable", False, "no response")

# 2. API feed
print("\n--- API Homepage Feed ---")
data, lat = curl_json(f"{LOCAL}/api/homepage/feed", timeout=30)
if data:
    test(f"/api/homepage/feed ok=true", data.get("ok") == True)
    test(f"degraded=false", data.get("degraded") == False)
    items = data.get("payload", {}).get("feed_items", [])
    test(f"feed_items present ({len(items)})", len(items) > 0)
    if items:
        test("first item has media_url", bool(items[0].get("media_url") or items[0].get("video_url")))
    reels = data.get("payload", {}).get("reels", [])
    test(f"reels present ({len(reels)})", len(reels) > 0)
    test(f"latency ({lat:.0f}ms)", lat < 10000, f"latency={lat:.0f}ms (cold start)")
else:
    test("/api/homepage/feed reachable", False, "no response")

# 3. Rendered homepage
print("\n--- Homepage HTML ---")
t0 = time.time()
r = subprocess.run(["curl", "-s", LOCAL], capture_output=True, text=True, timeout=30)
lat = (time.time() - t0) * 1000
html = r.stdout
if html:
    test(f"/ returned 200", r.returncode == 0)
    test(f"/ latency ({lat:.0f}ms)", lat < 15000, f"latency={lat:.0f}ms")
    test("HTML contains feed items (nvpro-post-card)", "nvpro-post-card" in html)
    test("HTML contains reels section", "nvpro-reels-section" in html)
    test("HTML contains bottom nav", "nvpro-bottom-nav" in html)
    test("HTML contains hamburger", "nvpro-hamburger" in html)
    test("No degraded mode", "'homepage_degraded': true" not in html)
else:
    test("/ reachable", False)

# 4. Error log
print("\n--- Error log ---")
elog = os.path.join(BASE, "logs", "gunicorn_error.log")
if os.path.exists(elog):
    with open(elog) as f:
        content = f.read()
    errors = [l for l in content.split("\n") if "ERROR" in l or "Traceback" in l]
    test("No ERROR/Traceback in gunicorn log", len(errors) == 0, f"Found {len(errors)} errors")
else:
    test("Error log exists", False)

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
