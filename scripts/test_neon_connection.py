import os, sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")

os.environ["CHAIN_FAST_LOCAL"] = "0"
os.environ["CHAIN_DISABLE_DB_PING"] = "0"
os.environ["CHAIN_DISABLE_SCHEMA_CHECK"] = "0"
os.environ["ENV"] = "production"
os.environ["FLASK_ENV"] = "production"

from services.neon_service import fast_query

print("DATABASE_URL:", "FOUND" if os.getenv("DATABASE_URL") else "MISSING")
print("FLASK_ENV:", os.getenv("FLASK_ENV"))
print("ENV:", os.getenv("ENV"))
print("CHAIN_FAST_LOCAL:", os.getenv("CHAIN_FAST_LOCAL"))

tests = [
    ("SELECT 1", "SELECT 1 AS ok"),
    ("chain_profiles", "SELECT id FROM chain_profiles LIMIT 1"),
    ("chain_posts", "SELECT id FROM chain_posts LIMIT 1"),
    ("chain_reels", "SELECT id FROM chain_reels LIMIT 1"),
    ("chain_status_posts", "SELECT id FROM chain_status_posts LIMIT 1"),
]

failed = False

for name, sql in tests:
    try:
        rows = fast_query(sql, timeout_ms=10000, default=None)
        print(f"{name}: OK -> {rows}")
    except Exception as e:
        failed = True
        print(f"{name}: FAILED -> {e}")

if failed:
    print("NEON CONNECTION TEST FAILED")
    sys.exit(1)

print("NEON CONNECTION TEST PASSED")
