"""Phase 157 Test G: Public engagement endpoints (like/comment)."""
import sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.engagement_service import toggle_like, add_comment
from services.neon_service import fast_query, write_query

def get_test_profiles(count=2):
    rows = fast_query(f"SELECT id FROM chain_profiles LIMIT {count}", default=[])
    return [str(r["id"]) for r in rows]

def run():
    profiles = get_test_profiles(2)
    if len(profiles) < 2:
        print("SKIP: Need at least 2 profiles in DB")
        return
    profile_id, liker_id = profiles[0], profiles[1]
    post_id = str(uuid.uuid4())
    reel_id = str(uuid.uuid4())
    story_id = str(uuid.uuid4())

    try:
        write_query(
            "INSERT INTO chain_posts (id, profile_id, caption, visibility, created_at) VALUES (%s, %s, %s, 'public', now()) ON CONFLICT (id) DO NOTHING",
            (post_id, profile_id, "Engagement test post")
        )
        write_query(
            "INSERT INTO chain_reels (id, profile_id, caption, video_url, visibility, created_at) VALUES (%s, %s, %s, %s, 'public', now()) ON CONFLICT (id) DO NOTHING",
            (reel_id, profile_id, "Engagement test reel", "https://example.com/vid.mp4")
        )
        write_query(
            "INSERT INTO chain_status_posts (id, profile_id, caption, visibility, expires_at, created_at, duration_seconds) VALUES (%s, %s, %s, 'public', now() + interval '24 hours', now(), 30) ON CONFLICT (id) DO NOTHING",
            (story_id, profile_id, "Engagement test story")
        )
    except Exception as e:
        print(f"SKIP: Could not insert test data - {e}")
        return

    res = toggle_like(liker_id, "post", post_id)
    assert res.get("success"), f"Like post failed: {res}"
    assert res.get("liked") == True

    res = toggle_like(liker_id, "post", post_id)
    assert res.get("success") and res.get("liked") == False

    res = toggle_like(liker_id, "reel", reel_id)
    assert res.get("success"), f"Like reel failed: {res}"

    res = toggle_like(liker_id, "story", story_id)
    assert res.get("success"), f"Like story failed: {res}"

    res = add_comment(liker_id, "post", post_id, "Test comment")
    assert res.get("success"), f"Comment on post failed: {res}"

    res = add_comment(liker_id, "reel", reel_id, "Test reel comment")
    assert res.get("success"), f"Comment on reel failed: {res}"

    write_query("DELETE FROM chain_post_reactions WHERE post_id = %s", (post_id,))
    write_query("DELETE FROM chain_reel_reactions WHERE reel_id = %s", (reel_id,))
    write_query("DELETE FROM chain_story_reactions WHERE story_id = %s", (story_id,))
    write_query("DELETE FROM chain_post_comments WHERE post_id = %s", (post_id,))
    write_query("DELETE FROM chain_reel_comments WHERE reel_id = %s", (reel_id,))
    write_query("DELETE FROM chain_posts WHERE id = %s", (post_id,))
    write_query("DELETE FROM chain_reels WHERE id = %s", (reel_id,))
    write_query("DELETE FROM chain_status_posts WHERE id = %s", (story_id,))
    print("PASS: test_phase157_public_engagement_counts")

if __name__ == "__main__":
    run()
