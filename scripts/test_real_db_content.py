import os
import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")

os.environ["CHAIN_FAST_LOCAL"] = "0"
os.environ["CHAIN_DISABLE_DB_PING"] = "0"
os.environ["CHAIN_DISABLE_SCHEMA_CHECK"] = "0"
os.environ["FLASK_ENV"] = "production"
os.environ["ENV"] = "production"

from services.neon_service import fast_query

print("Testing Neon persistence...")

tables = [
    "chain_profiles",
    "chain_posts",
    "chain_reels",
    "chain_status_posts"
]

for table in tables:
    rows = fast_query(
        f"SELECT COUNT(*) AS total FROM {table}",
        timeout_ms=10000,
        default=[]
    )
    print(table, rows)

print("Persistence test complete.")
