"""
Phase 60 Social Upgrade — Safe migration.
Creates missing tables/columns only if they do not exist.
"""
import os, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query

def _utcnow():
    return datetime.now(timezone.utc)

def table_exists(table):
    rows = fast_query(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s)",
        (table,), timeout_ms=5000, default=[]
    )
    return rows and rows[0].get("exists", False)

def column_exists(table, column):
    rows = fast_query(
        "SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s AND column_name = %s)",
        (table, column), timeout_ms=5000, default=[]
    )
    return rows and rows[0].get("exists", False)

def run(sql, desc):
    try:
        write_query(sql)
        print(f"  OK  {desc}")
    except Exception as e:
        print(f"  ERR {desc}: {e}")

MIGRATIONS = []

def add_table(name, create_sql):
    def migrate():
        if not table_exists(name):
            run(create_sql, f"Create table {name}")
        else:
            print(f"  SKIP {name} already exists")
    MIGRATIONS.append(migrate)

def add_column(table, column, alter_sql):
    def migrate():
        if not column_exists(table, column):
            run(alter_sql, f"Add column {table}.{column}")
        else:
            print(f"  SKIP {table}.{column} already exists")
    MIGRATIONS.append(migrate)

def add_index(name, create_sql):
    def migrate():
        run(create_sql, f"Create index {name}")
    MIGRATIONS.append(migrate)

# ── chain_reel_events ──
add_table("chain_reel_events", """
    CREATE TABLE chain_reel_events (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        reel_id UUID NOT NULL,
        user_id UUID,
        event_type TEXT NOT NULL DEFAULT 'view',
        watch_ms INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_reel_events_reel ON chain_reel_events(reel_id);
    CREATE INDEX IF NOT EXISTS idx_reel_events_user ON chain_reel_events(user_id);
""")

# ── chain_story_views (upgraded with reaction/reply) ──
add_table("chain_story_views", """
    CREATE TABLE chain_story_views (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        story_id UUID NOT NULL,
        viewer_id UUID,
        reaction TEXT,
        reply_text TEXT,
        created_at TIMESTAMPTZ DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_story_views_story ON chain_story_views(story_id);
""")

# ── chain_story_polls ──
add_table("chain_story_polls", """
    CREATE TABLE chain_story_polls (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        story_id UUID NOT NULL,
        question TEXT NOT NULL,
        options_json TEXT DEFAULT '[]',
        created_by UUID,
        expires_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_story_polls_story ON chain_story_polls(story_id);
""")

# ── chain_story_poll_votes ──
add_table("chain_story_poll_votes", """
    CREATE TABLE chain_story_poll_votes (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        poll_id UUID NOT NULL,
        user_id UUID NOT NULL,
        option_index INTEGER NOT NULL,
        created_at TIMESTAMPTZ DEFAULT now(),
        UNIQUE(poll_id, user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_story_poll_votes_poll ON chain_story_poll_votes(poll_id);
""")

# ── chain_comments (unified) ──
add_table("chain_comments", """
    CREATE TABLE chain_comments (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        content_type TEXT NOT NULL DEFAULT 'post',
        content_id UUID NOT NULL,
        parent_id UUID,
        user_id UUID NOT NULL,
        body TEXT NOT NULL,
        media_url TEXT,
        gif_url TEXT,
        reaction_type TEXT DEFAULT 'none',
        is_pinned BOOLEAN DEFAULT FALSE,
        is_deleted BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_comments_content ON chain_comments(content_type, content_id);
    CREATE INDEX IF NOT EXISTS idx_comments_parent ON chain_comments(parent_id);
    CREATE INDEX IF NOT EXISTS idx_comments_user ON chain_comments(user_id);
""")

# ── chain_comment_reactions ──
add_table("chain_comment_reactions", """
    CREATE TABLE chain_comment_reactions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        comment_id UUID NOT NULL,
        user_id UUID NOT NULL,
        reaction_type TEXT NOT NULL DEFAULT 'like',
        created_at TIMESTAMPTZ DEFAULT now(),
        UNIQUE(comment_id, user_id, reaction_type)
    );
    CREATE INDEX IF NOT EXISTS idx_comment_reactions_comment ON chain_comment_reactions(comment_id);
""")

# ── chain_creator_verifications ──
add_table("chain_creator_verifications", """
    CREATE TABLE chain_creator_verifications (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL,
        badge_type TEXT NOT NULL DEFAULT 'blue',
        status TEXT NOT NULL DEFAULT 'pending',
        evidence_url TEXT,
        reviewed_by UUID,
        reviewed_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_creator_verifications_user ON chain_creator_verifications(user_id);
    CREATE INDEX IF NOT EXISTS idx_creator_verifications_status ON chain_creator_verifications(status);
""")

# ── chain_follows (upgraded) ──
add_table("chain_follows", """
    CREATE TABLE chain_follows (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        follower_id UUID NOT NULL,
        following_id UUID NOT NULL,
        created_at TIMESTAMPTZ DEFAULT now(),
        UNIQUE(follower_id, following_id)
    );
    CREATE INDEX IF NOT EXISTS idx_follows_follower ON chain_follows(follower_id);
    CREATE INDEX IF NOT EXISTS idx_follows_following ON chain_follows(following_id);
""")

# ── chain_live_events (upgraded) ──
add_table("chain_live_events", """
    CREATE TABLE chain_live_events (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        room_id UUID NOT NULL,
        user_id UUID,
        event_type TEXT NOT NULL,
        payload_json TEXT DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_live_events_room ON chain_live_events(room_id);
    CREATE INDEX IF NOT EXISTS idx_live_events_type ON chain_live_events(event_type);
""")

# ── chain_message_reactions ──
add_table("chain_message_reactions", """
    CREATE TABLE chain_message_reactions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        message_id UUID NOT NULL,
        user_id UUID NOT NULL,
        reaction_type TEXT NOT NULL DEFAULT 'like',
        created_at TIMESTAMPTZ DEFAULT now(),
        UNIQUE(message_id, user_id, reaction_type)
    );
    CREATE INDEX IF NOT EXISTS idx_message_reactions_msg ON chain_message_reactions(message_id);
""")

# ── chain_message_receipts ──
add_table("chain_message_receipts", """
    CREATE TABLE chain_message_receipts (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        message_id UUID NOT NULL,
        user_id UUID NOT NULL,
        status TEXT NOT NULL DEFAULT 'sent',
        created_at TIMESTAMPTZ DEFAULT now(),
        UNIQUE(message_id, user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_message_receipts_msg ON chain_message_receipts(message_id);
    CREATE INDEX IF NOT EXISTS idx_message_receipts_user ON chain_message_receipts(user_id);
""")

# ── chain_message_attachments ──
add_table("chain_message_attachments", """
    CREATE TABLE chain_message_attachments (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        message_id UUID NOT NULL,
        attachment_type TEXT NOT NULL DEFAULT 'image',
        file_url TEXT,
        duration_ms INTEGER,
        waveform_json TEXT,
        created_at TIMESTAMPTZ DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_message_attachments_msg ON chain_message_attachments(message_id);
""")

# ── chain_saved_items ──
add_table("chain_saved_items", """
    CREATE TABLE chain_saved_items (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL,
        content_type TEXT NOT NULL DEFAULT 'post',
        content_id UUID NOT NULL,
        created_at TIMESTAMPTZ DEFAULT now(),
        UNIQUE(user_id, content_type, content_id)
    );
    CREATE INDEX IF NOT EXISTS idx_saved_items_user ON chain_saved_items(user_id);
    CREATE INDEX IF NOT EXISTS idx_saved_items_content ON chain_saved_items(content_type, content_id);
""")

# ── chain_regions ──
add_table("chain_regions", """
    CREATE TABLE chain_regions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        country TEXT DEFAULT 'Namibia',
        created_at TIMESTAMPTZ DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_regions_slug ON chain_regions(slug);
""")

# ── Existing table upgrades: add columns if missing ──
upgrade_columns = [
    ("chain_reels", "views_count", "ALTER TABLE chain_reels ADD COLUMN views_count INTEGER DEFAULT 0"),
    ("chain_reels", "duration_seconds", "ALTER TABLE chain_reels ADD COLUMN duration_seconds INTEGER DEFAULT 0"),
    ("chain_status_posts", "likes_count", "ALTER TABLE chain_status_posts ADD COLUMN likes_count INTEGER DEFAULT 0"),
    ("chain_status_posts", "comments_count", "ALTER TABLE chain_status_posts ADD COLUMN comments_count INTEGER DEFAULT 0"),
    ("chain_status_posts", "views_count", "ALTER TABLE chain_status_posts ADD COLUMN views_count INTEGER DEFAULT 0"),
    ("chain_live_rooms", "likes_count", "ALTER TABLE chain_live_rooms ADD COLUMN likes_count INTEGER DEFAULT 0"),
    ("chain_posts", "views_count", "ALTER TABLE chain_posts ADD COLUMN views_count INTEGER DEFAULT 0"),
    ("chain_posts", "shares_count", "ALTER TABLE chain_posts ADD COLUMN shares_count INTEGER DEFAULT 0"),
]
for tbl, col, sql in upgrade_columns:
    add_column(tbl, col, sql)

# ── Seed regions ──
def seed_regions():
    if not table_exists("chain_regions"):
        print("  SKIP seed regions: table does not exist")
        return
    regions = [
        ("Khomas", "khomas"),
        ("Erongo", "erongo"),
        ("Oshana", "oshana"),
        ("Ohangwena", "ohangwena"),
        ("Omusati", "omusati"),
        ("Oshikoto", "oshikoto"),
        ("Kavango East", "kavango-east"),
        ("Kavango West", "kavango-west"),
        ("Zambezi", "zambezi"),
        ("Otjozondjupa", "otjozondjupa"),
        ("Kunene", "kunene"),
        ("Hardap", "hardap"),
        ("Karas", "karas"),
        ("Omaheke", "omaheke"),
    ]
    for name, slug in regions:
        existing = fast_query("SELECT id FROM chain_regions WHERE slug = %s", (slug,), timeout_ms=3000, default=[])
        if not existing:
            try:
                write_query(
                    "INSERT INTO chain_regions (id, name, slug, country) VALUES (%s, %s, %s, 'Namibia')",
                    (str(uuid.uuid4()), name, slug)
                )
                print(f"  OK  Seed region: {name}")
            except Exception as e:
                print(f"  ERR Seed region {name}: {e}")
        else:
            print(f"  SKIP Region {name} already exists")

# ── Verify chain_follows has follower_profile_id/following_profile_id OR follower_id/following_id ──
def verify_follows():
    if not table_exists("chain_follows"):
        print("  SKIP verify follows: table does not exist")
        return
    has_cols = [c for c in ["follower_id","following_id","follower_profile_id","following_profile_id"] if column_exists("chain_follows", c)]
    print(f"  INFO chain_follows columns: {has_cols}")

# ── Run all ──
def main():
    print("\n=== Phase 60 Social Upgrade: Safe Migration ===\n")
    for i, migrate in enumerate(MIGRATIONS, 1):
        try:
            migrate()
        except Exception as e:
            print(f"  FAIL Migration {i}: {e}")
    print("\n--- Seeding regions ---")
    seed_regions()
    print("\n--- Verification ---")
    verify_follows()
    print("\n=== Phase 60 migration complete ===\n")

if __name__ == "__main__":
    main()
