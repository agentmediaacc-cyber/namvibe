#!/usr/bin/env python3
"""
Phase 131 — Mobile Chat Polish Test.
Verifies composer, bubbles, safe areas, draft autosave, typing indicator, scroll-to-bottom.
"""

import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASS = 0; FAIL = 0; WARN = 0
def ok(m): global PASS; PASS += 1; print(f"  [PASS] {m}")
def fail(m): global FAIL; FAIL += 1; print(f"  [FAIL] {m}")
def warn(m): global WARN; WARN += 1; print(f"  [WARN] {m}")
def read_file(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full): return ""
    with open(full, encoding="utf-8", errors="ignore") as f: return f.read()

css_chat = read_file("static/css/chat.css")
css_msg = read_file("static/css/namvibe_messages_pro.css")
js = read_file("static/js/namvibe_messages_pro.js")
inbox_html = read_file("templates/messages/inbox.html")
thread_html = read_file("templates/messages/thread.html")

print("=" * 60)
print("PHASE 131 — MOBILE CHAT POLISH TEST")
print("=" * 60)

print("\n--- 1. Message Bubbles ---")
ok("bubble styles") if ".msg" in css_chat or ".message-bubble" in css_chat else fail("bubble styles missing")
ok("max-width constraint") if "max-width" in css_chat else fail("max-width constraint missing")
ok("long text wrap") if "word-break" in css_chat or "overflow-wrap" in css_chat else fail("long text wrap missing")
ok("image responsive") if "max-width: 100%" in css_chat or "img" in css_chat and "max-width" in css_chat else warn("image responsive")
ok("video responsive") if "video" in css_chat and "max-width" in css_chat else warn("video responsive")

print("\n--- 2. Composer ---")
ok("composer exists") if "chat-composer" in css_chat or "composer" in css_chat else fail("composer missing")
ok("auto-grow") if "auto-grow" in js or "rows" in js or "scrollHeight" in js else warn("auto-grow composer")
ok("emoji picker") if "emoji" in js.lower() or "emoji" in inbox_html.lower() or "emoji" in thread_html.lower() else warn("emoji picker")
ok("attach button") if "attach" in js.lower() or "attachment" in css_chat else warn("attach button")
ok("voice note button") if "mic-btn" in js or "voice-record" in js else fail("voice note button missing")

print("\n--- 3. Mobile Layout ---")
ok("safe area padding") if "safe-area" in css_chat or "env(safe-area" in css_chat else warn("safe area padding")
ok("44px tap targets") if "44px" in css_chat or "min-height: 44" in css_chat or "min-width: 44" in css_chat else warn("44px tap targets")
ok("sticky composer") if "sticky" in css_chat and "bottom" in css_chat else warn("sticky composer")
ok("keyboard support") if "visual-viewport" in js or "keyboard" in js.lower() else warn("keyboard support")

print("\n--- 4. UX Features ---")
ok("draft autosave") if "draft" in js.lower() and "save" in js.lower() else warn("draft autosave")
ok("typing indicator") if "typing-indicator" in css_chat or "typing" in js else fail("typing indicator missing")
ok("unread badge") if "unread" in css_chat or "badge" in css_chat else warn("unread badge")
ok("scroll-to-bottom") if "scroll-to-bottom" in css_chat or "scrollToBottom" in js or "scrollToMessage" in js else warn("scroll-to-bottom button")

print(f"\n{'=' * 60}")
print("PHASE 131 — MOBILE CHAT POLISH TEST SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
