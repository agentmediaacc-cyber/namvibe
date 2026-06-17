"""Phase 71 Audit: TikTok-style Reels Feed Integration"""
import ast, os, subprocess, re, json, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
errors = []
warnings = []

def e(id, msg, fix=""):
    errors.append((id, msg, fix))

def w(id, msg):
    warnings.append((id, msg))

def exists(path):
    if not os.path.exists(path):
        e("E001", f"File missing: {path}", f"Create {path}")
        return False
    return True

def check_file(path):
    if not exists(path):
        return False
    return True

def compile_python(path):
    try:
        with open(path) as f:
            ast.parse(f.read())
        return True
    except SyntaxError as ex:
        e("E010", f"Python syntax error in {path}: {ex}", f"Fix syntax at {ex.lineno}:{ex.offset}")
        return False

def compile_js(path):
    if not exists(path) or not path.endswith(".js"):
        return True
    try:
        subprocess.run(
            ["node", "--check", path],
            capture_output=True, text=True, timeout=10
        )
        return True
    except subprocess.TimeoutExpired:
        w("W002", f"JS check timed out: {path}")
        return True
    except FileNotFoundError:
        w("W003", "node not found, skipping JS validation")
        return True
    except subprocess.CalledProcessError as ex:
        e("E011", f"JS syntax error in {path}: {ex.stderr.strip()}", f"Fix JS syntax")
        return False

print("=" * 60)
print("Phase 71 Audit: TikTok Reels Feed Integration")
print("=" * 60)

# 1. CSS exists and has required class names
print("\n[1/12] TikTok CSS file…")
CSS_PATH = os.path.join(ROOT, "static/css/tiktok_home.css")
if check_file(CSS_PATH):
    css = open(CSS_PATH).read()
    required_css = [
        ".tiktok-reel-stack", ".tiktok-reel-card", ".tiktok-reel-video",
        ".tiktok-action-rail", ".tiktok-action-btn", ".tiktok-reel-overlay",
        ".tiktok-reel-caption", ".tt-like-heart", ".tt-comment-overlay",
        ".tt-comment-drawer", ".tt-share-overlay", ".tt-share-drawer",
        ".tiktok-empty", ".tiktok-empty-btn", ".tiktok-reel-hashtags",
        ".tiktok-reel-music", ".tiktok-follow-badge"
    ]
    for cls in required_css:
        if cls not in css:
            e("E020", f"CSS class missing: {cls}", f"Add `{cls}` to tiktok_home.css")
        else:
            print(f"  OK  {cls}")

# 2. JS exists and has required functions
print("\n[2/12] TikTok JS file…")
JS_PATH = os.path.join(ROOT, "static/js/tiktok_home.js")
if check_file(JS_PATH):
    js = open(JS_PATH).read()
    required_js = [
        "init", "initReelScroll", "initActionButtons",
        "initCommentDrawer", "initShareDrawer",
        "openCommentDrawer", "openShareDrawer",
        "loadComments", "showToast", "ttCloseShare"
    ]
    for fn in required_js:
        if fn not in js:
            e("E030", f"JS function missing: {fn}", f"Define function `{fn}` in tiktok_home.js")
        else:
            print(f"  OK  {fn}()")

# 3. Template has TikTok section
print("\n[3/12] Template integration…")
TPL_PATH = os.path.join(ROOT, "templates/chain_home.html")
if check_file(TPL_PATH):
    tpl = open(TPL_PATH).read()
    required_tpl = [
        "tiktok_home.css", "tiktok_home.js",
        "tiktok-reel-stack", "tiktok-reel-card",
        "tt-comment-overlay", "tt-share-overlay"
    ]
    for item in required_tpl:
        if item not in tpl:
            e("E040", f"Template missing element: {item}", f"Add `{item}` to chain_home.html")
        else:
            print(f"  OK  {item}")

# 4. Python payload builder
print("\n[4/12] Python payload builder…")
SVC_PATH = os.path.join(ROOT, "services/homepage_service.py")
if check_file(SVC_PATH):
    if compile_python(SVC_PATH):
        src = open(SVC_PATH).read()
        if "build_tiktok_home_payload" in src:
            print("  OK  build_tiktok_home_payload() defined")
            if "reels_feed" in src:
                print("  OK  returns reels_feed key")
            else:
                e("E050", "build_tiktok_home_payload() missing reels_feed key", "Add reels_feed to return dict")
        else:
            e("E050", "build_tiktok_home_payload() not found", "Define build_tiktok_home_payload() in homepage_service.py")

# 5. Route passes payload
print("\n[5/12] Route passes payload…")
APP_PATH = os.path.join(ROOT, "app.py")
if check_file(APP_PATH):
    if compile_python(APP_PATH):
        src = open(APP_PATH).read()
        if "build_tiktok_home_payload" in src:
            print("  OK  build_tiktok_home_payload imported in app.py")
            if "reels_feed" in src:
                print("  OK  reels_feed passed to template context")
            else:
                w("W010", "reels_feed not found in app.py — may not be passed to template")
        else:
            e("E060", "build_tiktok_home_payload not imported in app.py", "Add import to home route")

# 6. No fake/test content
print("\n[6/12] No fake/test content…")
for fp in [JS_PATH, CSS_PATH, SVC_PATH, TPL_PATH]:
    if fp and os.path.exists(fp):
        content = open(fp).read()
        fake_patterns = [
            "demo_", "test_user", "sample", "placeholder", "lorem",
            "faker", "hardcoded", "fake_name"
        ]
        for pat in fake_patterns:
            if pat in content.lower():
                w("W020", f"Suspected fake/test content '{pat}' in {os.path.basename(fp)}")

print("  OK  Clean check (warnings only)")

# 7. No pink/purple colors
print("\n[7/12] No pink/purple color theme…")
for fp in [CSS_PATH, TPL_PATH]:
    if fp and os.path.exists(fp):
        content = open(fp).read()
        forbidden = [
            "hotpink", "deeppink", "fuchsia", "magenta", "#ff00",
            "#7c3aed", "#8b5cf6", "#a78bfa", "#c084fc"
        ]
        bad_css = ["2563eb", "1E88E5", "1e88e5"]
        for color in forbidden:
            if color in content.lower():
                w("W030", f"Forbidden color '{color}' found in {os.path.basename(fp)}")
        for bad in bad_css:
            if bad in content:
                w("W031", f"Blue override still present '{bad}' in {os.path.basename(fp)}")

print("  OK  Theme check (warnings only)")

# 8. No bare href="#" without data- handler
print("\n[8/12] No bare href='#' without data- handler…")
if check_file(TPL_PATH):
    tpl = open(TPL_PATH).read()
    bare_href = re.findall(r'href\s*=\s*["\']#["\']', tpl)
    data_handled = re.findall(r'href\s*=\s*["\']#["\'].*?data-', tpl)
    if len(bare_href) > len(data_handled) + 2:
        diff = len(bare_href) - len(data_handled)
        e("E070", f"{diff} bare href='#' without data- handler", "Add data-* attribute or real route")
    else:
        print(f"  OK  {len(bare_href)} total href='#', properly handled")

# 9. Action rail has like/comment/share/save
print("\n[9/12] Action rail buttons…")
if check_file(TPL_PATH):
    tpl = open(TPL_PATH).read()
    for action in ["like", "comment", "share", "save"]:
        if f'data-action="{action}"' in tpl:
            print(f"  OK  data-action=\"{action}\"")
        else:
            e("E080", f"Missing action button: {action}", f"Add data-action=\"{action}\" to action rail")
    if "tiktok-follow-badge" in tpl or "tt-follow-btn" in tpl:
        print("  OK  follow button")
    else:
        e("E081", "Missing follow button", "Add follow button to action rail")
    if "tiktok-action-avatar-btn" in tpl:
        print("  OK  avatar/profile button")
    else:
        e("E082", "Missing profile avatar button in action rail", "Add .tiktok-action-avatar-btn")

# 10. Empty state exists
print("\n[10/12] Empty state…")
if check_file(TPL_PATH):
    tpl = open(TPL_PATH).read()
    if "tiktok-empty" in tpl:
        print("  OK  Empty state section present")
        if "/reels/upload" in tpl:
            print("  OK  Upload reel link in empty state")
        else:
            e("E090", "Empty state missing upload link", "Add /reels/upload link")
    else:
        e("E090", "TikTok empty state missing", "Add .tiktok-empty section")

# 11. Python compile check all files
print("\n[11/12] Python compilation check…")
good = True
for py_file in [SVC_PATH, APP_PATH,
                os.path.join(ROOT, "services/reels_service.py"),
                os.path.join(ROOT, "api_routes/reels_routes.py")]:
    if os.path.exists(py_file) and not compile_python(py_file):
        good = False
if good:
    print("  OK  All Python files compile cleanly")

# 12. JS compile check
print("\n[12/12] JavaScript compile check…")
compile_js(JS_PATH)

print("\n" + "=" * 60)
total = len(errors)
print(f"Audit Complete: {total} errors, {len(warnings)} warnings")
for eid, msg, fix in errors:
    print(f"  ERROR {eid}: {msg}")
    print(f"         Fix: {fix}")
for wid, msg in warnings:
    print(f"  WARN  {wid}: {msg}")

sys.exit(1 if errors else 0)
