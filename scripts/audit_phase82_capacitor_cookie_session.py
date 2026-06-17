#!/usr/bin/env python3
"""
Audit Phase 82 – Capacitor WebView Cookie Session Configuration.
Checks that all Android / Capacitor settings are correct for cookie-based session
persistence over cleartext HTTP on 192.168.179.30:5000.
"""

import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FAILED = False

EXPECTED_HOST = "http://192.168.179.30:5000"
EXPECTED_IP = "192.168.179.30"
FORBIDDEN = ["localhost", "127.0.0.1"]


def check(label: str, ok: bool, detail: str = ""):
    global FAILED
    status = "PASS" if ok else "FAIL"
    if not ok:
        FAILED = True
    print(f"  [{status}] {label}" + (f"  | {detail}" if detail else ""))


def read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


# ---------------------------------------------------------------------------
# 1. capacitor.config.json
# ---------------------------------------------------------------------------
print("=" * 72)
print("1. capacitor.config.json")
print("=" * 72)

cap_path = REPO / "mobile_android" / "capacitor.config.json"
cap_raw = read_file(cap_path)

try:
    cap = json.loads(cap_raw)
except json.JSONDecodeError as e:
    cap = {}
    check("capacitor.config.json is valid JSON", False, str(e))

server = cap.get("server", {})
android_cfg = cap.get("android", {})

check("server.url == EXPECTED_HOST", server.get("url") == EXPECTED_HOST,
      f"got {server.get('url')!r}")
check("server.cleartext is true", server.get("cleartext") is True,
      f"got {server.get('cleartext')!r}")
check("android.allowMixedContent is true", android_cfg.get("allowMixedContent") is True,
      f"got {android_cfg.get('allowMixedContent')!r}")
check("android.webContentsDebuggingEnabled is true",
      android_cfg.get("webContentsDebuggingEnabled") is True,
      f"got {android_cfg.get('webContentsDebuggingEnabled')!r}")

# allowNavigation must include the target host
nav = server.get("allowNavigation", [])
has_ip_nav = any(EXPECTED_IP in entry for entry in nav)
check("allowNavigation includes 192.168.179.30:*", has_ip_nav,
      f"entries: {nav}")

# No forbidden hosts
for host in FORBIDDEN:
    if host in cap_raw:
        check(f"No forbidden host '{host}' in capacitor.config.json", False,
              f"found '{host}'")
    else:
        check(f"No forbidden host '{host}' in capacitor.config.json", True)

# ---------------------------------------------------------------------------
# 2. AndroidManifest.xml
# ---------------------------------------------------------------------------
print("\n" + "=" * 72)
print("2. AndroidManifest.xml")
print("=" * 72)

manifest_path = REPO / "mobile_android" / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
manifest_raw = read_file(manifest_path)

check("android:usesCleartextTraffic=\"true\" present",
      'usesCleartextTraffic="true"' in manifest_raw or 'usesCleartextTraffic="true"' in manifest_raw,
      "checked for attribute")
check("android:networkSecurityConfig reference present",
      'networkSecurityConfig' in manifest_raw)

for host in FORBIDDEN:
    if host in manifest_raw:
        check(f"No forbidden host '{host}' in AndroidManifest", False,
              f"found '{host}'")
    else:
        check(f"No forbidden host '{host}' in AndroidManifest", True)

# ---------------------------------------------------------------------------
# 3. network_security_config.xml
# ---------------------------------------------------------------------------
print("\n" + "=" * 72)
print("3. network_security_config.xml")
print("=" * 72)

netsec_path = REPO / "mobile_android" / "android" / "app" / "src" / "main" / "res" / "xml" / "network_security_config.xml"
netsec_raw = read_file(netsec_path)

check("network_security_config.xml exists", netsec_path.exists())
check("cleartextTrafficPermitted=\"true\" present",
      'cleartextTrafficPermitted="true"' in netsec_raw)
check("domain 192.168.179.30 present", EXPECTED_IP in netsec_raw,
      f"content includes {EXPECTED_IP}")

# ---------------------------------------------------------------------------
# 4. MainActivity.java – CookieManager
# ---------------------------------------------------------------------------
print("\n" + "=" * 72)
print("4. MainActivity.java – CookieManager")
print("=" * 72)

main_act_path = (REPO / "mobile_android" / "android" / "app" / "src" / "main"
                 / "java" / "com" / "namvibe" / "app" / "MainActivity.java")
main_raw = read_file(main_act_path)

check("CookieManager.getInstance() present", "CookieManager.getInstance()" in main_raw)
check("setAcceptCookie(true) present", "setAcceptCookie(true)" in main_raw)
check("setAcceptThirdPartyCookies present", "setAcceptThirdPartyCookies" in main_raw)
check("cookieManager.flush() present", "cookieManager.flush()" in main_raw)
check("APP_HOST constant = EXPECTED_HOST", EXPECTED_HOST in main_raw,
      "checked for http://192.168.179.30:5000")
check("WebView debug logging present", "logDebugInfo" in main_raw)
check("fetch(/auth/debug-session) present", "/auth/debug-session" in main_raw)

for host in FORBIDDEN:
    if host in main_raw:
        check(f"No forbidden host '{host}' in MainActivity.java", False,
              f"found '{host}'")
    else:
        check(f"No forbidden host '{host}' in MainActivity.java", True)

# ---------------------------------------------------------------------------
# 5. No stale host references across mobile_android
# ---------------------------------------------------------------------------
print("\n" + "=" * 72)
print("5. Stale host references scan")
print("=" * 72)

EXCLUDE_DIRS = {"node_modules", ".gradle", "build", "intermediates"}
stale_found = False
mobile_root = REPO / "mobile_android"
for fpath in mobile_root.rglob("*"):
    if fpath.is_dir():
        continue
    if any(p.name in EXCLUDE_DIRS for p in fpath.relative_to(mobile_root).parents):
        continue
    if fpath.suffix in (".pyc", ".png", ".jpg", ".jar", ".aar", ".dex", ".so", ".class"):
        continue
    try:
        text = fpath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    for bad in FORBIDDEN:
        if bad not in text:
            continue
        lines = text.splitlines()
        for ln in lines:
            if bad in ln:
                check(f"Stale host '{bad}' in {fpath.relative_to(mobile_root)}", False, ln.strip())
                stale_found = True
                break

if not stale_found:
    check("No stale localhost/127.0.0.1 references", True)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 72)
if FAILED:
    print("AUDIT: FAILED – one or more checks did not pass.")
    sys.exit(1)
else:
    print("AUDIT: ALL CHECKS PASSED.")
    sys.exit(0)
