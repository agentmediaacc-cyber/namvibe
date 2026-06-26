#!/usr/bin/env python3
"""Phase 164: Audit that notification event types match between engagement_service and notification_engine."""
import sys, os, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASS = 0
FAIL = 0

def check(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}  {detail}")

def extract_event_types(filepath):
    """Extract event_type strings from the file."""
    content = open(filepath).read()
    types = set()
    for m in re.finditer(r'"event_type":\s*"([^"]+)"', content):
        types.add(m.group(1))
    return types

engagement = "services/engagement_service.py"
notif_engine = "services/notification_engine.py"

print("=== Phase 164 — Notification Event Types Audit ===")

engagement_types = extract_event_types(engagement)
notif_categories = set()
notif_icons = set()
content = open(notif_engine).read()
for m in re.finditer(r'"([^"]+)":\s*"(activity|mentions|system|messages)"', content):
    notif_categories.add(m.group(1))
for m in re.finditer(r'"([^"]+)":\s*"fa-[^"]+"', content):
    notif_icons.add(m.group(1))

all_notif_keys = notif_categories | notif_icons

# Check each engagement event type has a matching notification entry
for etype in sorted(engagement_types):
    has_category = etype in notif_categories
    has_icon = etype in notif_icons
    check(f"event_type '{etype}' has notification category",
          has_category, f"missing from _NOTIF_TYPE_CATEGORIES")
    check(f"event_type '{etype}' has notification icon",
          has_icon, f"missing from _NOTIF_ICONS")

# Verify specific expected pairs
expected = [
    ("post_like", "activity", "fa-heart"),
    ("reel_like", "activity", "fa-heart"),
    ("comment", "activity", "fa-comment"),
]
for etype, expected_cat, expected_icon in expected:
    cat_match = re.search(rf'"{etype}":\s*"({expected_cat})"', content)
    icon_match = re.search(rf'"{etype}":\s*"({expected_icon})"', content)
    check(f"'{etype}' → category '{expected_cat}'", bool(cat_match))
    check(f"'{etype}' → icon '{expected_icon}'", bool(icon_match))

print(f"\nResults: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
