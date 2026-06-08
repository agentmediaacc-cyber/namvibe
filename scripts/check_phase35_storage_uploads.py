#!/usr/bin/env python3
"""Phase 35 — Storage / Upload Infrastructure Check"""

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

passed = 0
failed = 0

STATUS = {"ready": [], "partial": [], "missing": [], "provider_required": []}

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
        STATUS["ready"].append(name)
    else:
        print(f"  [FAIL] {name} {detail}")
        failed += 1
        if "required" in detail.lower():
            STATUS["provider_required"].append(name)
        else:
            STATUS["missing"].append(name)

# 1. Storage service exists
svc_file = os.path.join(BASE, "services", "storage_service.py")
check("Storage service (storage_service.py) exists", os.path.exists(svc_file))

# 2. Upload routes exist
routes_file = os.path.join(BASE, "api_routes", "profile_routes.py")
upload_routes = False
if os.path.exists(routes_file):
    content = open(routes_file).read()
    if "upload" in content.lower():
        upload_routes = True
check("Upload routes in profile_routes.py", upload_routes)

# 3. Message attachment upload route
try:
    from services.message_feature_service import save_attachment
    check("Message attachment upload (save_attachment)", callable(save_attachment))
except Exception:
    check("Message attachment upload (save_attachment)", False, "save_attachment not found")

# 4. Voice note upload route
try:
    from services.message_feature_service import save_voice_note
    check("Voice note upload (save_voice_note)", callable(save_voice_note))
except Exception:
    check("Voice note upload (save_voice_note)", False, "save_voice_note not found")

# 5. Status upload route
try:
    from services.status_service import create_status
    check("Status upload (create_status)", callable(create_status))
except Exception:
    # Try storage_service
    try:
        from services.storage_service import upload_status_media
        check("Status upload (upload_status_media)", callable(upload_status_media))
    except Exception:
        check("Status upload route", False, "No status upload function found")

# 6. Reel upload route
try:
    from services.reel_processing_engine import process_reel
    check("Reel upload (process_reel)", callable(process_reel))
except Exception:
    try:
        from services.reels_engine import upload_reel
        check("Reel upload (upload_reel)", callable(upload_reel))
    except Exception:
        check("Reel upload function", False, "No reel upload function found")

# 7. Profile avatar/cover upload
try:
    from services.storage_service import upload_avatar, upload_cover
    check("Avatar upload (upload_avatar)", callable(upload_avatar))
    check("Cover upload (upload_cover)", callable(upload_cover))
except Exception as e:
    check("Avatar/cover upload functions", False, str(e))

# 8. Storage bucket env presence
bucket_env = False
env_file = os.path.join(BASE, ".env")
if os.path.exists(env_file):
    env_content = open(env_file).read()
    if "SUPABASE_URL" in env_content or "BUCKET" in env_content or "STORAGE" in env_content:
        bucket_env = True
check("Storage bucket env present (SUPABASE_URL)", bucket_env, "No storage env vars found")

# 9. Graceful fallback if provider missing
try:
    from utils.supabase_client import get_supabase_admin
    check("Supabase client importable", True)
except Exception as e:
    check("Supabase client importable", False, str(e))

# 10. Media storage service exists
media_storage_file = os.path.join(BASE, "services", "media_storage_service.py")
check("Media storage service exists", os.path.exists(media_storage_file))

# 11. Uploaded files directory exists
uploads_dir = os.path.join(BASE, "static", "uploads")
if os.path.isdir(uploads_dir):
    check("Static uploads directory exists", True)
else:
    check("Static uploads directory exists", False, "static/uploads/ not found — may need local fallback")

# 12. Supabase bucket names defined
try:
    from services.media_storage_service import SUPPORTED_BUCKETS
    check(f"Supported buckets defined ({len(SUPPORTED_BUCKETS)})", len(SUPPORTED_BUCKETS) > 0)
except Exception:
    check("Supported buckets defined", False, "No SUPPORTED_BUCKETS found")

print()
print("  [SUMMARY] Storage/Upload Infrastructure:")
print(f"    Ready: {len(STATUS['ready'])}")
print(f"    Missing: {len(STATUS['missing'])}")
print(f"    Provider required: {len(STATUS['provider_required'])}")
print()
print(f"Results: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")
if failed > 0:
    sys.exit(1)
