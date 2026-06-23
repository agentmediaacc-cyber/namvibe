#!/usr/bin/env python3
"""
Phase 154 — Media Routes Audit
Scans app.py + api_routes/ for duplicate or conflicting create/upload/delete/media routes.
"""

import re, sys, os, glob as glob_mod
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_DIR = os.path.join(ROOT, "api_routes")
APP_PY = os.path.join(ROOT, "app.py")
JS_FILE = os.path.join(ROOT, "static/js/namvibe_home_pro.js")

results = []  # list of (str, str) -> (check_name, status)  status: PASS/FAIL/WARN
details = []


def check(name, status, msg=""):
    results.append((name, status))
    if msg:
        details.append(f"  [{status}] {name}: {msg}")


# ── 1. Parse app.py routes ──
def parse_app_routes():
    routes = []
    if not os.path.isfile(APP_PY):
        check("Parse app.py", "FAIL", "File not found")
        return routes
    with open(APP_PY) as f:
        content = f.read()

    pattern = re.compile(
        r'@app\.route\([\'"]([^\'"]+)[\'"]\s*(?:,\s*methods=\[([^\]]*)\])?\)\s*\n\s*def\s+(\w+)'
    )
    for m in pattern.finditer(content):
        path = m.group(1)
        methods_raw = m.group(2)
        fn = m.group(3)
        methods = []
        if methods_raw:
            methods = re.findall(r"[\"']([^\"']+)[\"']", methods_raw)
        if not methods:
            methods = ["GET"]
        routes.append((path, methods, fn, "app.py"))
    return routes


# ── 2. Parse api_routes blueprint routes ──
def parse_blueprint_routes():
    routes = []
    if not os.path.isdir(API_DIR):
        check("Parse api_routes", "FAIL", "Directory not found")
        return routes

    for fpath in sorted(glob_mod.glob(os.path.join(API_DIR, "*.py"))):
        fname = os.path.basename(fpath)
        with open(fpath) as f:
            content = f.read()

        # Extract Blueprint url_prefix
        bp_match = re.search(
            r'Blueprint\([\'"]([^\'"]+)[\'"]\s*,.*?url_prefix=[\'"]([^\'"]+)[\'"]',
            content,
        )
        if not bp_match:
            continue
        prefix = bp_match.group(2).rstrip("/")

        # Find decorator routes
        for m in re.finditer(
            r'@(\w+)\.route\([\'"]([^\'"]+)[\'"]\s*(?:,\s*methods=\[([^\]]*)\])?\)\s*\n\s*def\s+(\w+)',
            content,
        ):
            bp_var = m.group(1)
            path = m.group(2)
            methods_raw = m.group(3)
            fn = m.group(4)
            methods = []
            if methods_raw:
                methods = re.findall(r"[\"']([^\"']+)[\"']", methods_raw)
            if not methods:
                methods = ["GET"]
            full_path = prefix + ("/" if not path.startswith("/") else "") + path
            routes.append((full_path, methods, fn, fname))
    return routes


# ── 3. Build full URL list ──
app_routes = parse_app_routes()
bp_routes = parse_blueprint_routes()

all_routes = app_routes + bp_routes

print(f"\n{'='*60}")
print(f"  Phase 154 — Media Routes Audit Report")
print(f"{'='*60}")
print(f"\nRoutes found: {len(app_routes)} in app.py, {len(bp_routes)} in blueprints")
print(f"  Total: {len(all_routes)}")
print()

# Group by path+method for duplicate detection
from collections import defaultdict

route_map = defaultdict(list)  # (path, method) -> [(fn, source)]
for path, methods, fn, src in all_routes:
    for m in methods:
        route_map[(path, m)].append((fn, src))


# ── 4. Detect duplicate routes ──
dup_count = 0
for (path, method), entries in sorted(route_map.items()):
    if len(entries) > 1:
        dup_count += 1
        sources = ", ".join(f"{e[1]}:{e[0]}" for e in entries)
        check(
            f"Duplicate: {method} {path}",
            "FAIL",
            f"Registered {len(entries)}x — {sources}",
        )

if dup_count == 0:
    check("Duplicate route detection", "PASS", "No duplicate routes found")

print()

# ── 5. Detect standards violations ──

# 5a: /create routes that don't use save_media_file() or content_service
create_routes = [(p, m, fn, src) for p, m, fn, src in all_routes if p.endswith("/create")]
for path, methods, fn, src in create_routes:
    fpath = APP_PY if src == "app.py" else os.path.join(API_DIR, src)
    if not os.path.isfile(fpath):
        continue
    with open(fpath) as f:
        content = f.read()
    uses_save = "save_media_file" in content
    uses_content = "content_service" in content
    uses_create_fn = "create_status" in content or "create_post" in content or "create_reel" in content
    if not (uses_save or uses_content):
        check(
            f"Standards: {path} (in {src})",
            "WARN",
            f"Uses neither save_media_file() nor content_service (uses_create={uses_create_fn})",
        )

# 5b: /delete routes that don't handle Supabase cleanup
delete_routes = [(p, m, fn, src) for p, m, fn, src in all_routes if p.endswith("/delete")]
for path, methods, fn, src in delete_routes:
    fpath = APP_PY if src == "app.py" else os.path.join(API_DIR, src)
    if not os.path.isfile(fpath):
        continue
    with open(fpath) as f:
        content = f.read()
    has_supabase_cleanup = "delete_status" in content or "delete_post" in content or "delete_reel" in content or "delete_story" in content or "delete_comment" in content
    if not has_supabase_cleanup:
        check(
            f"Standards: {path} (in {src})",
            "WARN",
            "No supabase delete function call detected",
        )

# 5c: Routes with /status/ and /stories/ doing the same thing
status_vs_stories = [(p, m, fn, src) for p, m, fn, src in all_routes
                     if "/status/" in p and ("create" in p or "/delete" in p)]
stories_vs_status = [(p, m, fn, src) for p, m, fn, src in all_routes
                     if "/stories" in p and ("create" in p or "/delete" in p)]
if status_vs_stories:
    check(
        "Route overlap: /status/ vs /stories/",
        "WARN",
        f"/status/create+delete: {[r[0] for r in status_vs_stories]} — overlapping concern with /stories/*",
    )

# 5d: Duplicate POST routes to /api/.../create
api_create_map = defaultdict(list)
for path, methods, fn, src in all_routes:
    if "/api/" in path and path.endswith("/create") and "POST" in methods:
        api_create_map[path].append((fn, src, methods))
for path, entries in sorted(api_create_map.items()):
    if len(entries) > 1:
        sources = "; ".join(f"{e[1]}:{e[0]}({','.join(e[2])})" for e in entries)
        check(
            f"Duplicate API create: {path}",
            "FAIL",
            f"Multiple definitions — {sources}",
        )

# 5e: Check that status_routes.py has both /status/ and /status/stories/ (overlap)
status_routes_path = os.path.join(API_DIR, "status_routes.py")
if os.path.isfile(status_routes_path):
    with open(status_routes_path) as f:
        sr_content = f.read()
    if "/stories" in sr_content:
        check(
            "status_routes.py: /status/stories route",
            "WARN",
            "Blueprint for /status contains /status/stories redirect — potential confusion with /stories/*",
        )

# 5f: Check stories_v2_routes.py has duplicate view/reply routes internally
stories_v2_path = os.path.join(API_DIR, "stories_v2_routes.py")
if os.path.isfile(stories_v2_path):
    with open(stories_v2_path) as f:
        sv2 = f.read()
    internal_dupes = defaultdict(list)
    for m in re.finditer(
        r'@(\w+)\.route\([\'"]([^\'"]+)[\'"]\s*(?:,\s*methods=\[([^\]]*)\])?\)\s*\n\s*def\s+(\w+)',
        sv2,
    ):
        path = m.group(2)
        fn = m.group(4)
        internal_dupes[path].append(fn)
    for path, fns in sorted(internal_dupes.items()):
        if len(fns) > 1:
            check(
                f"stories_v2_routes.py: {path}",
                "FAIL",
                f"Defined {len(fns)}x internally: {', '.join(fns)}",
            )


# ── 6. Check JS URLs ──
if not os.path.isfile(JS_FILE):
    check("JS URL audit", "FAIL", f"JS file not found at {JS_FILE}")
else:
    with open(JS_FILE) as f:
        js = f.read()

    # Expected standardized create endpoints
    expected_create = {
        "/api/posts/create": "Post create",
        "/api/reels/create": "Reel create",
        "/api/stories/create": "Story create",
    }

    for url, label in expected_create.items():
        if url in js:
            check(f"JS URL: {url}", "PASS", f"Found in JS — {label}")
        else:
            check(f"JS URL: {url}", "FAIL", f"Not found in JS — expected {label}")

    # Check that the upload URL mapping in JS is correct
    upload_line = None
    for line in js.split("\n"):
        if "uploadUrl = type === " in line or "uploadUrl" in line and "posts/create" in line:
            upload_line = line.strip()
    if upload_line:
        check("JS upload URL mapping", "PASS", f"Found: {upload_line}")
    else:
        # Check the alternative pattern
        for line in js.split("\n"):
            if "/api/posts/create" in line and "type" in line:
                upload_line = line.strip()
                check("JS upload URL mapping", "PASS", f"Found: {upload_line}")
                break
        else:
            check("JS upload URL mapping", "WARN", "Could not confirm upload URL mapping in JS")

    # Verify reels like/save URLs in JS point to the correct blueprint-prefixed paths
    # JS calls /api/reels/<id>/like but the blueprint route is /reels/api/reels/<id>/like
    like_pattern = re.search(r'"/api/reels/"\s*\+\s*id\s*\+\s*"/like"', js)
    save_pattern = re.search(r'"/api/reels/"\s*\+\s*id\s*\+\s*"/save"', js)

    if like_pattern:
        check(
            "JS: /api/reels/<id>/like",
            "WARN",
            "JS uses /api/reels/<id>/like — but blueprint route is /reels/api/reels/<id>/like (may 404)",
        )
    else:
        check("JS: /api/reels/<id>/like", "PASS", "Reel like URL not found (or uses correct path)")

    if save_pattern:
        check(
            "JS: /api/reels/<id>/save",
            "WARN",
            "JS uses /api/reels/<id>/save — but blueprint route is /reels/api/reels/<id>/save (may 404)",
        )
    else:
        check("JS: /api/reels/<id>/save", "PASS", "Reel save URL not found (or uses correct path)")

    # Check that view batch URL is correct
    if "/reels/api/reels/view/batch" in js:
        check("JS: /reels/api/reels/view/batch", "PASS", "Correctly uses blueprint-prefixed path")
    else:
        check("JS: /reels/api/reels/view/batch", "WARN", "Not found or uses different path")


# ── 7. Print final report ──
print(f"\n{'─'*60}")
print(f"  RESULTS SUMMARY")
print(f"{'─'*60}")
print(f"  {'Check':<50} {'Status':<8}")
print(f"  {'─'*50} {'─'*8}")
for name, status in results:
    short = name[:48] + ".." if len(name) > 50 else name
    print(f"  {short:<50} {status:<8}")

pass_count = sum(1 for _, s in results if s == "PASS")
fail_count = sum(1 for _, s in results if s == "FAIL")
warn_count = sum(1 for _, s in results if s == "WARN")

print(f"\n{'─'*60}")
print(f"  PASS: {pass_count}  |  FAIL: {fail_count}  |  WARN: {warn_count}")
print(f"  {'ALL CHECKS PASSED' if fail_count == 0 else 'SOME CHECKS FAILED — review details above'}")
print(f"{'='*60}\n")

if details:
    print("Details:")
    for d in details:
        print(d)
    print()
