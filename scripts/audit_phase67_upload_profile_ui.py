#!/usr/bin/env python3
"""Phase 67 audit: verify safe_upload_file, template fixes, reconnect debounce, profile UI."""

import os, sys, re, compileall
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(str(ROOT))

errors = []

def check(name, ok, detail=""):
    if ok:
        print(f"  [PASS] {name}")
    else:
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))
        errors.append(name)

def file_contains(path, pattern):
    try:
        text = Path(path).read_text()
        return bool(re.search(pattern, text, re.I))
    except Exception:
        return False

print("=== PHASE 67 AUDIT: Upload, Profile UI, Reconnect, Sound ===\n")

# ── 1. safe_upload_file exists ──
print("1. safe_upload_file helper")
src = Path("services/storage_service.py").read_text()
check("safe_upload_file function defined", "def safe_upload_file" in src)
check("LOCAL_UPLOAD_DIRS dict defined", "LOCAL_UPLOAD_DIRS" in src)
check("'_save_to_local' helper defined", "def _save_to_local" in src)
check("story upload dir in LOCAL_UPLOAD_DIRS", "\"story\": \"static/uploads/stories\"" in src)
check("avatar upload dir in LOCAL_UPLOAD_DIRS", "\"avatar\": \"static/uploads/profile/avatars\"" in src)
check("post upload dir in LOCAL_UPLOAD_DIRS", "\"post\": \"static/uploads/posts\"" in src)
check("reel upload dir in LOCAL_UPLOAD_DIRS", "\"reel\": \"static/uploads/reels\"" in src)

# ── 2. Local upload folders exist ──
print("\n2. Local upload folders")
for key, folder in [
    ("stories", "static/uploads/stories"),
    ("posts", "static/uploads/posts"),
    ("profile/avatars", "static/uploads/profile/avatars"),
    ("covers", "static/uploads/profile/covers"),
    ("reels", "static/uploads/reels"),
]:
    check(f"'{folder}' directory exists", Path(folder).exists(), f"missing: {folder}")
    if not Path(folder).exists():
        try:
            Path(folder).mkdir(parents=True, exist_ok=True)
            check(f"'{folder}' created", True)
        except Exception:
            pass

# ── 3. Bucket not found NOT in templates ──
print("\n3. Bucket error not rendered in templates")
bucket_errors = []
for tpl in sorted(Path("templates").rglob("*.html")):
    text = tpl.read_text()
    if "Bucket not found" in text or "bucket not found" in text:
        bucket_errors.append(str(tpl.relative_to(ROOT)))
check("No bucket errors in templates", len(bucket_errors) == 0, f"found in {bucket_errors}")

# ── 4. Test call sound not in base template for normal users ──
print("\n4. Test call sound restricted to admin pages")
base_html = Path("templates/base.html").read_text()
has_path_check = "path.startsWith" in base_html and ("/admin" in base_html or "/developer" in base_html)
check("addUnlockButton checks path before showing", has_path_check, "missing path check")

# ── 5. Reconnect banner has debounce ──
print("\n5. Reconnect toast debounce")
check("setTimeout for reconnecting exists", "setTimeout" in base_html and ("chain-reconnect-banner" in base_html), "missing reconnect debounce")
check("initialConnectDone flag exists", "initialConnectDone" in base_html, "missing initial connect flag")
check("3 second delay exists", "3000" in base_html, "missing 3000ms delay")

# ── 6. safe_upload_file used in status_service ──
print("\n6. Story upload uses safe_upload_file")
status_svc = Path("services/status_service.py").read_text()
check("safe_upload_file imported in status_service", "safe_upload_file" in status_svc)
check("upload_story_media NOT imported directly", "from services.supabase_storage_router import upload_story_media" not in status_svc)

# ── 7. safe_upload_file used in profile_service for avatar/cover ──
print("\n7. Profile avatar/cover uses safe_upload_file")
profile_svc = Path("services/profile_service.py").read_text()
check("safe_upload_file used in upload_profile_avatar", "safe_upload_file(file_obj, \"avatar\"" in profile_svc)
check("safe_upload_file used in upload_profile_cover", "safe_upload_file(file_obj, \"cover\"" in profile_svc)

# ── 8. Compile check ──
print("\n8. Python compilation check")
success = compileall.compile_dir(str(ROOT), quiet=2, force=True, rx=re.compile(r'/(\.git|node_modules|__pycache__|\.venv)/'))
check("All .py files compile cleanly", success, "compile errors found")

# ── 9. Profile avatar fallback initials exist in templates ──
print("\n9. Profile avatar fallback initials")
check("profile_header has initials fallback", re.search(r'\[0\]\s*\|upper', Path("templates/profile/partials/profile_header.html").read_text()) is not None)
check("profile index has initials fallback", re.search(r'\[0\]\s*\|upper', Path("templates/profile/index.html").read_text()) is not None)

# ── 10. Reconnect banner HTML exists ──
print("\n10. Reconnect banner element")
check("chain-reconnect-banner div exists", "chain-reconnect-banner" in base_html)

print(f"\n{'='*40}")
print(f"RESULTS: {len(errors)} failures out of {20 - len(['safe_upload_file'])} checks")
if errors:
    print(f"FAILURES: {errors}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED")
