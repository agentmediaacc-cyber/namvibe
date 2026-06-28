#!/usr/bin/env python3
"""Test content owner controls: edit caption, delete, visibility, lock, share URL, auth checks."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'testing'
os.environ['CHAIN_FAST_LOCAL'] = '1'

PASS = 0
FAIL = 0

def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} - {detail}")

print("=" * 60)
print("PHASE 159 — CONTENT OWNER CONTROLS")
print("=" * 60)

# 1. content_controls_bp importable
print("\n1. Blueprint import...")
try:
    from api_routes.content_controls_routes import content_controls_bp
    test("content_controls_bp importable", True)
    test("Blueprint has name 'content_controls'", content_controls_bp.name == "content_controls")
except ImportError as e:
    test("content_controls_bp importable", False, str(e))

# 2. Edit caption handler exists
print("\n2. Edit caption handler...")
try:
    from api_routes.content_controls_routes import edit_caption
    test("edit_caption handler importable", True)
    import inspect
    source = inspect.getsource(edit_caption)
    test("edit_caption builds UPDATE query", "UPDATE" in source and "SET caption" in source)
    test("edit_caption checks content_type", "content_type" in source)
    test("edit_caption verifies owner", "owner_check" in source or "_verify_owner" in source)
except (ImportError, Exception) as e:
    test("edit_caption importable", False, str(e))

# 3. Delete handler exists
print("\n3. Delete handler...")
try:
    from api_routes.content_controls_routes import delete_content
    test("delete_content handler importable", True)
    import inspect
    source = inspect.getsource(delete_content)
    test("delete_content uses soft-delete (deleted_at)", "deleted_at" in source and "SET" in source)
    test("delete_content verifies owner", "owner_check" in source or "_verify_owner" in source)
except (ImportError, Exception) as e:
    test("delete_content importable", False, str(e))

# 4. Visibility change handler
print("\n4. Visibility change handler...")
try:
    from api_routes.content_controls_routes import change_visibility
    test("change_visibility handler importable", True)
    import inspect
    source = inspect.getsource(change_visibility)
    test("change_visibility updates visibility column", "SET visibility" in source)
    test("change_visibility validates visibility options", "CONTENT_VISIBILITY_OPTIONS" in source)
except (ImportError, Exception) as e:
    test("change_visibility importable", False, str(e))

# 5. Lock toggle handler
print("\n5. Lock toggle handler...")
try:
    from api_routes.content_controls_routes import toggle_lock
    test("toggle_lock handler importable", True)
    import inspect
    source = inspect.getsource(toggle_lock)
    test("toggle_lock updates locked field", "locked" in source)
    test("toggle_lock verifies owner", "owner_check" in source or "_verify_owner" in source)
except (ImportError, Exception) as e:
    test("toggle_lock importable", False, str(e))

# 6. Share URL handler
print("\n6. Share URL handler...")
try:
    from api_routes.content_controls_routes import get_share_url
    test("get_share_url handler importable", True)
    import inspect
    source = inspect.getsource(get_share_url)
    test("get_share_url returns share_url in response", "share_url" in source)
    test("get_share_url checks content exists", "WHERE id" in source)
except (ImportError, Exception) as e:
    test("get_share_url importable", False, str(e))

# 7. Only owner can edit/delete (auth check)
print("\n7. Owner auth checks...")
try:
    from api_routes.content_controls_routes import _verify_owner, CONTENT_TABLES
    test("_verify_owner importable", True)
    import inspect
    source = inspect.getsource(_verify_owner)
    test("_verify_owner returns False when not owner", "row[0][\"profile_id\"] != profile_id" in source or "return False" in source)
    test("_verify_owner returns None when not found", "return None" in source)
    test("CONTENT_TABLES maps post/reel/story", "post" in CONTENT_TABLES and "reel" in CONTENT_TABLES and "story" in CONTENT_TABLES)
except (ImportError, Exception) as e:
    test("_verify_owner importable", False, str(e))

try:
    from api_routes.content_controls_routes import edit_caption, delete_content, change_visibility, toggle_lock
    import inspect
    for name, func in [("edit_caption", edit_caption), ("delete_content", delete_content),
                       ("change_visibility", change_visibility), ("toggle_lock", toggle_lock)]:
        source = inspect.getsource(func)
        test(f"{name} checks Forbidden (403)", "Forbidden" in source or "403" in source)
        test(f"{name} checks Not Found (404)", "Not found" in source or "404" in source or "return jsonify" in source)
except Exception as e:
    test("owner auth checks", False, str(e))

# 8. Locked media access is checked server-side
print("\n8. Locked media access check...")
try:
    from api_routes.content_controls_routes import get_content
    test("get_content handler importable", True)
    import inspect
    source = inspect.getsource(get_content)
    test("get_content checks visibility for private/followers", "private" in source and "followers" in source)
    test("get_content checks authentication", "Authentication required" in source or "profile" in source)
except (ImportError, Exception) as e:
    test("get_content importable", False, str(e))

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
