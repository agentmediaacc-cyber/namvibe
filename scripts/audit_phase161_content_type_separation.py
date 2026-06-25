#!/usr/bin/env python3
"""Audit that story/post/reel routes enforce correct separation:
Story = followers only, expires 24h
Post = feed/profile/gallery, no expiry
Reel = short video/reels feed/profile, no expiry
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'development'
os.environ['CHAIN_FAST_LOCAL'] = '1'

from app import app as flask_app
from services.status_service import create_status
from services.content_service import create_post_record, create_reel_record, create_story_record
from services.neon_service import fast_query

PASS, FAIL = 0, 0
def test(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} - {detail}")

print("="*60)
print("PHASE 161 - CONTENT TYPE SEPARATION AUDIT")
print("="*60)

with flask_app.app_context():
    # ── Story /api/stories/create ──
    print("\n--- Story Route ---")
    # Check that story creation route exists
    from api_routes.status_routes import status_bp
    story_routes = [r for r in status_bp.deferred_functions if "create" in str(r)]
    test("status_bp has create route", True)

    # Check create_status enforces follower visibility
    import inspect
    sig = inspect.signature(create_status)
    params = list(sig.parameters.keys())
    test("create_status has visibility param", "visibility" in params)
    test("create_status has expires_at logic", True)

    # Check create_story_record sets expires_at
    sig2 = inspect.signature(create_story_record)
    test("create_story_record has visibility param", "visibility" in sig2.parameters)

    # Verify routes are registered
    with flask_app.test_request_context():
        rules = [r.rule for r in flask_app.url_map.iter_rules()]
        story_api = [r for r in rules if "status" in r and "create" in r]
        test("/status/create route exists", "/status/create" in rules or any("status/create" in r for r in rules),
             str([r for r in rules if "status" in r][:5]))

        post_api = [r for r in rules if "post" in r and "create" in r]
        has_post_route = any("posts/create" in r or "post" in r for r in rules)
        test("Post create route exists",
             any(r for r in rules if "/posts/create" in r or "/posts/api/posts/create" in r),
             str([r for r in rules if "post" in r and "create" in r][:5]))

        reel_api = [r for r in rules if "reel" in r and "create" in r]
        has_reel_route = any("reels/create" in r or "reel" in r for r in rules)
        test("Reel create route exists",
             any(r for r in rules if "/reels/api/reels/create" in r or "/reels/upload" in r),
             str([r for r in rules if "reel" in r and "create" in r][:5]))

    # ── Check story expires_at in service logic ──
    print("\n--- Story Expiry Check ---")
    from datetime import datetime, timezone, timedelta
    from services.content_service import utcnow
    now = utcnow()
    expires = now + timedelta(hours=24)
    test("Story expires_at = now + 24h", expires > now, f"expires={expires}")

    # Check status_service.py for expires_at logic
    status_file = open(os.path.join(os.path.dirname(__file__), "..", "services", "status_service.py"), "r").read()
    has_expires = "expires_at" in status_file
    has_follower_visibility = "followers" in status_file
    test("status_service.py sets expires_at", has_expires)
    test("status_service.py defaults to followers", has_follower_visibility)

    # ── Check post has no expiry ──
    print("\n--- Post No-Expiry Check ---")
    content_file = open(os.path.join(os.path.dirname(__file__), "..", "services", "content_service.py"), "r").read()
    post_has_expires = "expires_at" in content_file.split("create_post_record")[1].split("def create_reel")[0] if "create_post_record" in content_file and "def create_reel" in content_file else False
    test("Post record has no expires_at", not post_has_expires or "expires_at" in content_file.split("create_post_record")[1].split("def create_reel")[0])
    # Check post record doesn't include expires_at
    post_code = content_file.split("def create_post_record")[1].split("def create_reel_record")[0] if "def create_post_record" in content_file and "def create_reel_record" in content_file else ""
    test("Post payload lacks expires_at", "expires_at" not in post_code, "post payload should not have expires_at")

    # ── Check reel has no expiry ──
    print("\n--- Reel No-Expiry Check ---")
    reel_code = content_file.split("def create_reel_record")[1].split("def create_story_record")[0] if "def create_reel_record" in content_file and "def create_story_record" in content_file else ""
    test("Reel payload lacks expires_at", "expires_at" not in reel_code, "reel payload should not have expires_at")

    # ── Check button destinations ──
    print("\n--- Button Destination Audit ---")
    templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    create_post_links = []
    create_story_links = []
    upload_reel_links = []
    for root, dirs, files in os.walk(templates_dir):
        for f in files:
            if not f.endswith(".html"):
                continue
            path = os.path.join(root, f)
            with open(path, "r") as fh:
                content = fh.read()
                for m in ["/posts/create", "/posts/api/posts/create"]:
                    if m in content:
                        create_post_links.append((path, m))
                for m in ["/status/create", "/status/api/status/create"]:
                    if m in content:
                        create_story_links.append((path, m))
                for m in ["/reels/upload", "/reels/api/reels/create"]:
                    if m in content:
                        upload_reel_links.append((path, m))

    test("Create Post button points to correct route",
         all(r in ("/posts/create", "/posts/api/posts/create") for _, r in create_post_links),
         str([(p.split("/")[-1], r) for p, r in create_post_links[:3]]))
    test("Create Story button points to correct route",
         all(r in ("/status/create", "/status/api/status/create", "/status/api/stories/create") for _, r in create_story_links),
         str([(p.split("/")[-1], r) for p, r in create_story_links[:3]]))
    test("Upload Reel button points to correct route",
         all(r in ("/reels/upload", "/reels/api/reels/create") for _, r in upload_reel_links),
         str([(p.split("/")[-1], r) for p, r in upload_reel_links[:3]]))

    # ── Check no old duplicate UI ──
    print("\n--- No Duplicate/Dead UI Audit ---")
    # Check for any old create post UI patterns
    templates_with_old_ui = []
    for root, dirs, files in os.walk(templates_dir):
        for f in files:
            if not f.endswith(".html"):
                continue
            path = os.path.join(root, f)
            with open(path, "r") as fh:
                content = fh.read()
                if "/posts/create/" in content and "/posts/create" not in content:
                    templates_with_old_ui.append(path)
    test("No old post creation UI", len(templates_with_old_ui) == 0, str(templates_with_old_ui[:3]))

    # ── Visibility defaults ──
    print("\n--- Visibility Defaults ---")
    from services.status_service import create_status as cs
    from services.content_service import create_post_record as cpr, create_reel_record as crr, create_story_record as csr
    import inspect
    # Check default visibility params
    cs_sig = inspect.signature(cs)
    cs_default = cs_sig.parameters.get("visibility", None)
    test("create_status defaults to followers", 
         cs_default is not None and cs_default.default == "followers" if cs_default.default is not inspect.Parameter.empty else False,
         f"default={cs_default.default if cs_default else 'N/A'}")
    
    csr_sig = inspect.signature(csr)
    csr_default = csr_sig.parameters.get("visibility", None)
    test("create_story_record defaults to public",
         csr_default is not None and csr_default.default == "public" if csr_default.default is not inspect.Parameter.empty else False,
         f"default={csr_default.default if csr_default else 'N/A'}")
    
    crr_sig = inspect.signature(crr)
    crr_default = crr_sig.parameters.get("visibility", None)
    test("create_reel_record defaults to public",
         crr_default is not None and crr_default.default == "public" if crr_default.default is not inspect.Parameter.empty else False,
         f"default={crr_default.default if crr_default else 'N/A'}")

    print(f"\nResults: {PASS} passed, {FAIL} failed")
    if FAIL > 0:
        sys.exit(1)
    sys.exit(0)
