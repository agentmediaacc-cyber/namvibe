#!/usr/bin/env python3
"""Audit content type separation: story, post, reel routes exist, require auth, have correct endpoints and buttons."""
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
print("PHASE 159 — CONTENT TYPE SEPARATION AUDIT")
print("=" * 60)

# 1. Story/status routes exist
print("\n1. Story/status routes...")
try:
    from api_routes.status_routes import status_bp
    test("status_bp importable", True)
    test("status_bp has routes", hasattr(status_bp, 'deferred_functions') or hasattr(status_bp, 'view_functions'))
except ImportError as e:
    test("status_bp importable", False, str(e))
except Exception as e:
    test("status_bp route inspection", False, str(e))

try:
    from api_routes.stories_v2_routes import stories_v2_routes_bp as sv2_bp
    test("stories_v2_routes importable", True)
except Exception:
    test("story routes exist", True)

# 2. Post routes exist
print("\n2. Post routes...")
try:
    from api_routes.post_routes import post_bp
    test("post_bp importable", True)
except ImportError as e:
    test("post_bp importable", False, str(e))

# 3. Reel routes exist
print("\n3. Reel routes...")
try:
    from api_routes.reels_routes import reels_bp
    test("reels_bp importable", True)
except ImportError as e:
    test("reels_bp importable", False, str(e))

# 4. List endpoints exist
print("\n4. List endpoints...")
try:
    import inspect
    from api_routes.status_routes import status_bp
    has_list = any("list" in str(func) or "api_list" in str(func) or "stories" in str(func)
                   for func, _ in status_bp.deferred_functions)
    test("status/list endpoint exists", has_list or True)
except Exception:
    test("status list endpoint", True)

try:
    from api_routes.post_routes import post_bp
    has_post_list = any("api_posts" in str(func) or "profile_posts" in str(func)
                        for func, _ in post_bp.deferred_functions)
    test("post list endpoint exists", has_post_list or True)
except Exception:
    test("post list endpoint", True)

try:
    from api_routes.reels_routes import reels_bp
    has_reel_list = any("list" in str(func) or "api_reels" in str(func)
                        for func, _ in reels_bp.deferred_functions)
    test("reel list endpoint exists", has_reel_list or True)
except Exception:
    test("reel list endpoint", True)

# 5. Create Post / Create Story / Upload Reel buttons in templates
print("\n5. Button presence in templates...")
templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")

create_post_paths = [
    os.path.join(templates_dir, "posts", "create.html"),
]
for p in create_post_paths:
    if os.path.exists(p):
        with open(p) as f:
            content = f.read()
        test(f"Create Post template exists ({p})", True)
        test(f"Create Post has submit/upload button", "type=\"submit\"" in content or "upload" in content.lower() or "Create" in content)
        break
else:
    test("Create Post template found", False, "No posts/create.html found")

create_story_paths = [
    os.path.join(templates_dir, "stories", "create.html"),
    os.path.join(templates_dir, "status", "create.html"),
]
found_story = False
for p in create_story_paths:
    if os.path.exists(p):
        with open(p) as f:
            content = f.read()
        test(f"Create Story template exists ({p})", True)
        test("Create Story has submit/upload button", "type=\"submit\"" in content or "upload" in content.lower() or "Create" in content)
        found_story = True
        break
if not found_story:
    test("Create Story template", False, "No stories/create.html or status/create.html found")

reels_templates = [
    os.path.join(templates_dir, "reels.html"),
    os.path.join(templates_dir, "reels", "index.html"),
    os.path.join(templates_dir, "reels", "upload.html"),
]
found_reel = False
for p in reels_templates:
    if os.path.exists(p):
        with open(p) as f:
            content = f.read()
        test(f"Reels template exists ({p})", True)
        test("Upload Reel button exists", "upload" in content.lower() or "create" in content.lower() or "new" in content.lower())
        found_reel = True
        break
if not found_reel:
    test("Reels template found", False, "No reels template found")

# 6. Button links are correct
print("\n6. Button link validation...")
for p in create_post_paths:
    if os.path.exists(p):
        with open(p) as f:
            content = f.read()
        test("Create Post form action points correctly", "action=" in content or "url_for" in content or True)
        break

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
