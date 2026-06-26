#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"

echo ""
echo "============================================"
echo " Phase 164 — Full Verification Suite"
echo "============================================"
echo ""

PASS=0
FAIL=0
SCRIPTS=(
  "scripts/test_phase164_likes_optimistic_ui.py"
  "scripts/test_phase164_comments_instant.py"
  "scripts/test_phase164_story_music_trim.py"
  "scripts/test_phase164_multi_picture_story.py"
  "scripts/test_phase164_reels_upload_reliability.py"
  "scripts/test_phase164_video_compression.py"
  "scripts/audit_phase164_notification_event_types.py"
  "scripts/audit_phase164_optimistic_contract.py"
)

for script in "${SCRIPTS[@]}"; do
  if python3 "$script"; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
  fi
  echo ""
done

echo "============================================"
echo " Scripts: $PASS passed, $FAIL failed"
echo "============================================"

echo ""
echo "--- Python compile check ---"
python3 -m py_compile services/engagement_service.py
python3 -m py_compile services/status_service.py
python3 -m py_compile services/video_processing_service.py
python3 -m py_compile api_routes/reels_routes.py
python3 -m py_compile api_routes/status_routes.py
echo "All Python files compile OK"

echo ""
echo "============================================"
if [ "$FAIL" -eq 0 ]; then
  echo " SUCCESS: All Phase 164 checks pass!"
else
  echo " WARNING: $FAIL script(s) failed"
  exit 1
fi
echo "============================================"
