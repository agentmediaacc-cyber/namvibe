#!/usr/bin/env bash
set -e

echo "======================================"
echo "CHAIN CRITICAL FIX PHASE"
echo "======================================"

cd ~/Desktop/chain_app
source venv/bin/activate

echo ""
echo "1) CHECK ENV FLAGS"
echo "--------------------------------------"
echo "DATABASE_URL exists?"
python3 - <<'PY'
import os
from dotenv import load_dotenv
load_dotenv(dotenv_path='.env')
url=os.getenv("DATABASE_URL","")
print("DATABASE_URL:", "FOUND" if url else "MISSING")
if url:
    print("DATABASE_URL starts:", url[:25] + "...")
for k in [
 "CHAIN_FAST_LOCAL",
 "CHAIN_DISABLE_DB_PING",
 "CHAIN_DISABLE_SCHEMA_CHECK",
 "CHAIN_DISABLE_PREWARM",
 "FLASK_ENV",
 "ENV"
]:
    print(k, "=", os.getenv(k))
PY

echo ""
echo "2) FIND FAST LOCAL FLAGS"
echo "--------------------------------------"
grep -R "CHAIN_FAST_LOCAL\|schema_check_skipped_fast_local\|FAST_LOCAL\|DISABLE_DB_PING" . \
  --exclude-dir=venv --exclude-dir=.git || true

echo ""
echo "3) CREATE NEON CONNECTION TEST"
echo "--------------------------------------"
cat > scripts/test_neon_connection.py <<'PY'
import os, sys
from dotenv import load_dotenv
load_dotenv(dotenv_path='.env')

os.environ["CHAIN_FAST_LOCAL"] = "0"
os.environ["CHAIN_DISABLE_DB_PING"] = "0"
os.environ["CHAIN_DISABLE_SCHEMA_CHECK"] = "0"
os.environ["ENV"] = "production"
os.environ["FLASK_ENV"] = "production"

try:
    from services.neon_service import fast_query, get_pool
except Exception as e:
    print("IMPORT FAILED:", e)
    sys.exit(1)

print("DATABASE_URL:", "FOUND" if os.getenv("DATABASE_URL") else "MISSING")

try:
    pool = get_pool()
    print("POOL:", "OK" if pool else "NONE")
except Exception as e:
    print("POOL ERROR:", e)

tests = [
    ("SELECT 1", "SELECT 1 AS ok"),
    ("chain_profiles", "SELECT id FROM chain_profiles LIMIT 1"),
    ("chain_posts", "SELECT id FROM chain_posts LIMIT 1"),
]

all_ok = True
for name, sql in tests:
    try:
        rows = fast_query(sql, timeout_ms=8000, default=None)
        print(name, "OK", rows)
    except Exception as e:
        all_ok = False
        print(name, "FAILED:", e)

if not all_ok:
    sys.exit(1)

print("NEON CONNECTION TEST PASSED")
PY

echo ""
echo "4) RUN NEON CONNECTION TEST"
echo "--------------------------------------"
python3 scripts/test_neon_connection.py || {
  echo ""
  echo "NEON FAILED."
  echo "Fix DATABASE_URL in .env first."
  echo "Make sure Neon URL looks like:"
  echo "postgresql://USER:PASSWORD@HOST.neon.tech/DB?sslmode=require"
  exit 1
}

echo ""
echo "5) CREATE REAL DB CONTENT TEST"
echo "--------------------------------------"
cat > scripts/test_real_db_content.py <<'PY'
import os, uuid, sys
from dotenv import load_dotenv
load_dotenv(dotenv_path='.env')

os.environ["CHAIN_FAST_LOCAL"] = "0"
os.environ["CHAIN_DISABLE_DB_PING"] = "0"
os.environ["CHAIN_DISABLE_SCHEMA_CHECK"] = "0"
os.environ["ENV"] = "production"
os.environ["FLASK_ENV"] = "production"

from services.neon_service import fast_query, write_query

profile_id = None

profiles = fast_query("SELECT id FROM chain_profiles LIMIT 1", timeout_ms=8000, default=[])
if profiles:
    profile_id = profiles[0]["id"]
else:
    profile_id = str(uuid.uuid4())
    write_query("""
        INSERT INTO chain_profiles (id, username, display_name, email, created_at, updated_at)
        VALUES (%s, %s, %s, %s, now(), now())
        ON CONFLICT (id) DO NOTHING
    """, (profile_id, "test_user_db", "Test User DB", f"test-{uuid.uuid4()}@chain.local"))

print("USING PROFILE:", profile_id)

post_id = str(uuid.uuid4())
write_query("""
    INSERT INTO chain_posts (id, profile_id, body, caption, post_type, visibility, created_at)
    VALUES (%s, %s, %s, %s, 'text', 'public', now())
""", (post_id, profile_id, "Real DB test post", "Real DB test post"))

post = fast_query("SELECT id FROM chain_posts WHERE id=%s", (post_id,), timeout_ms=8000, default=[])
assert post, "post not persisted"
print("POST OK:", post_id)

reel_id = str(uuid.uuid4())
write_query("""
    INSERT INTO chain_reels (id, profile_id, caption, video_url, media_url, visibility, status, created_at)
    VALUES (%s, %s, %s, %s, %s, 'public', 'published', now())
""", (reel_id, profile_id, "Real DB test reel", "/static/test.mp4", "/static/test.mp4"))

reel = fast_query("SELECT id FROM chain_reels WHERE id=%s", (reel_id,), timeout_ms=8000, default=[])
assert reel, "reel not persisted"
print("REEL OK:", reel_id)

story_id = str(uuid.uuid4())
write_query("""
    INSERT INTO chain_status_posts (id, profile_id, caption, media_type, visibility, expires_at, created_at)
    VALUES (%s, %s, %s, 'text', 'public', now() + interval '24 hours', now())
""", (story_id, profile_id, "Real DB test story"))

story = fast_query("SELECT id FROM chain_status_posts WHERE id=%s", (story_id,), timeout_ms=8000, default=[])
assert story, "story not persisted"
print("STORY OK:", story_id)

print("REAL DB CONTENT TEST PASSED")
PY

python3 scripts/test_real_db_content.py

echo ""
echo "6) CHECK STORY ROUTE FILE"
echo "--------------------------------------"
grep -n "status_bp.route.*create\|def create\|redirect\|create_status" api_routes/status_routes.py || true

echo ""
echo "7) COMPILE"
echo "--------------------------------------"
python3 -m py_compile app.py services/*.py api_routes/*.py

echo ""
echo "8) PYTHON VERSION WARNING"
echo "--------------------------------------"
python3 --version
echo "Recommended production version: Python 3.12"

echo ""
echo "CRITICAL FIX CHECK COMPLETE"
