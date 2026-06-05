import os
from dotenv import load_dotenv
import psycopg2

load_dotenv(".env")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not found")

sql = """
CREATE INDEX IF NOT EXISTS idx_posts_created
ON chain_posts(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_posts_profile
ON chain_posts(profile_id);

CREATE INDEX IF NOT EXISTS idx_reels_created
ON chain_reels(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_reels_profile
ON chain_reels(profile_id);

CREATE INDEX IF NOT EXISTS idx_status_created
ON chain_status_posts(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_live_created
ON chain_live_rooms(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notifications_recipient
ON chain_notifications(recipient_profile_id, is_read);

CREATE INDEX IF NOT EXISTS idx_messages_thread
ON chain_messages(thread_id);

CREATE INDEX IF NOT EXISTS idx_thread_members_profile
ON chain_thread_members(profile_id);

CREATE INDEX IF NOT EXISTS idx_profiles_username
ON chain_profiles(username);

CREATE INDEX IF NOT EXISTS idx_posts_visibility
ON chain_posts(visibility);

CREATE INDEX IF NOT EXISTS idx_reels_visibility
ON chain_reels(visibility);

CREATE INDEX IF NOT EXISTS idx_status_expires
ON chain_status_posts(expires_at);

CREATE INDEX IF NOT EXISTS idx_messages_sender
ON chain_messages(sender_profile_id);

CREATE INDEX IF NOT EXISTS idx_notifications_created
ON chain_notifications(created_at DESC);
"""

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True

cur = conn.cursor()
cur.execute(sql)

cur.close()
conn.close()

print("================================")
print("CHAIN INDEX OPTIMIZATION COMPLETE")
print("================================")
