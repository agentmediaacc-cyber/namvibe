#!/usr/bin/env python3
"""Audit offline upload draft system."""

import re, sys

issues = []

# Check offline cache has draft support
with open("static/js/namvibe_offline_cache.js") as f:
    oc = f.read()
    if "saveDraft" not in oc:
        issues.append("offline_cache.js: missing saveDraft")
    if "getDrafts" not in oc:
        issues.append("offline_cache.js: missing getDrafts")
    if "deleteDraft" not in oc:
        issues.append("offline_cache.js: missing deleteDraft")

# Check home_pro.js disables uploads when offline
with open("static/js/namvibe_home_pro.js") as f:
    hp = f.read()
    if "data-open-camera" not in hp:
        issues.append("home_pro.js: missing data-open-camera in offline disable")
    if "disabled" not in hp.split("function updateOfflineBanner")[1].split("function showToast")[0]:
        issues.append("home_pro.js: upload not disabled when offline")
    if "Upload unavailable" not in hp:
        issues.append("home_pro.js: missing 'Upload unavailable' message")

# Check camera creator checks network before upload
with open("static/js/namvibe_camera_creator.js") as f:
    cjs = f.read()
    if "onerror" not in cjs:
        issues.append("cam_creator.js: missing upload error handling")
    if "Network error" not in cjs:
        issues.append("cam_creator.js: missing network error message")

if issues:
    for i in issues:
        print(f"UPLOAD DRAFT: {i}")
    sys.exit(1)
else:
    print("PART E OK: Offline upload queue/draft system is properly wired")