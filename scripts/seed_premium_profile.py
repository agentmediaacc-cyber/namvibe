#!/usr/bin/env python3
"""Seed real data into premium profile tables for a test profile."""

import os, sys, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["FLASK_ENV"] = "development"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["ALLOW_LOCAL_AUTH_FALLBACK"] = "true"

from services.neon_service import fast_query, write_query
from services.supabase_safe import safe_insert


def get_profile(username="alpha_user"):
    rows = fast_query(
        "SELECT id, username, display_name FROM chain_profiles WHERE username = %s AND deleted_at IS NULL LIMIT 1",
        [username], default=[]
    )
    return rows[0] if rows else None


def update_profile_columns(pid):
    updates = {
        "pronouns": "they/them",
        "occupation": "Full-Stack Developer",
        "company": "NamVibe Inc.",
        "school": "Windhoek High School",
        "university": "University of Namibia",
        "mood_emoji": "🚀",
        "mood_text": "Building the future",
        "current_activity": "🎥 Recording Reel",
        "quote_of_day": "Code is poetry in motion.",
        "activity_status": "online",
        "profile_score": 87,
        "profile_level": "Gold",
        "member_since": "2024-01-15T00:00:00+00:00",
        "country_flag": "🇳🇦",
        "city_name": "Windhoek",
        "trust_score": 94,
        "community_rating": 4.7,
        "friendliness_score": 92,
        "safety_score": 88,
        "response_rate": 96,
        "response_time": "< 15 min",
        "popularity_score": 78,
        "activity_level": 85,
        "premium_badge": True,
        "creator_badge": True,
        "identity_verified": True,
        "scam_protection": True,
        "local_time": "14:30",
        "weather_emoji": "☀️",
        "weather_temp": "32°C",
        "total_profile_views": 15420,
        "total_post_likes": 8921,
        "total_comments": 2341,
        "total_shares": 567,
        "total_bookmarks": 1234,
        "total_achievements": 8,
        "total_collections": 5,
    }
    for col, val in updates.items():
        write_query(
            f"UPDATE chain_profiles SET {col} = %s WHERE id = %s",
            (val, pid)
        )
    print(f"  ✓ profile columns updated ({len(updates)} cols)")


def seed_education(pid):
    data = [
        {"institution": "University of Namibia", "degree": "B.Sc. Computer Science",
         "field_of_study": "Software Engineering", "start_year": 2020, "end_year": 2024},
        {"institution": "Windhoek High School", "degree": "High School Diploma",
         "field_of_study": "Science & Math", "start_year": 2016, "end_year": 2020},
    ]
    for d in data:
        write_query(
            "INSERT INTO chain_education (profile_id, institution, degree, field_of_study, start_year, end_year) "
            "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (pid, d["institution"], d["degree"], d["field_of_study"], d["start_year"], d["end_year"])
        )
    print(f"  ✓ education seeded ({len(data)} entries)")


def seed_work(pid):
    data = [
        {"company": "NamVibe Inc.", "position": "Senior Full-Stack Developer",
         "location": "Windhoek, Namibia", "start_year": 2024, "is_current": True},
        {"company": "TechStartup Namibia", "position": "Junior Developer",
         "location": "Windhoek, Namibia", "start_year": 2022, "end_year": 2024},
    ]
    for d in data:
        write_query(
            "INSERT INTO chain_work_experience (profile_id, company, position, location, start_year, end_year, is_current) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (pid, d["company"], d["position"], d["location"], d["start_year"], d.get("end_year"), d.get("is_current", False))
        )
    print(f"  ✓ work experience seeded ({len(data)} entries)")


def seed_skills(pid):
    data = [
        {"skill": "Python", "category": "Programming", "proficiency": 95, "is_top": True},
        {"skill": "JavaScript", "category": "Programming", "proficiency": 90, "is_top": True},
        {"skill": "React", "category": "Frontend", "proficiency": 88, "is_top": True},
        {"skill": "Flask", "category": "Backend", "proficiency": 92, "is_top": True},
        {"skill": "PostgreSQL", "category": "Database", "proficiency": 85, "is_top": True},
        {"skill": "UI/UX Design", "category": "Design", "proficiency": 72},
        {"skill": "DevOps", "category": "Infrastructure", "proficiency": 68},
        {"skill": "Machine Learning", "category": "AI", "proficiency": 55},
    ]
    for d in data:
        write_query(
            "INSERT INTO chain_user_skills (profile_id, skill_name, category, proficiency, is_top) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (profile_id, skill_name) DO UPDATE SET proficiency = EXCLUDED.proficiency",
            (pid, d["skill"], d["category"], d["proficiency"], d.get("is_top", False))
        )
    print(f"  ✓ skills seeded ({len(data)} entries)")


def seed_visitors(pid):
    # Get some other profiles as visitors
    others = fast_query(
        "SELECT id, username, display_name FROM chain_profiles WHERE id != %s AND deleted_at IS NULL LIMIT 5",
        [pid], default=[]
    )
    for o in others:
        write_query(
            "INSERT INTO chain_profile_visitors (profile_id, visitor_id) VALUES (%s, %s) "
            "ON CONFLICT (profile_id, visitor_id) DO UPDATE SET visited_at = now()",
            (pid, o["id"])
        )
    print(f"  ✓ visitors seeded ({len(others)} entries)")


def seed_activity(pid):
    data = [
        ("post_created", "Posted a new photo", "post", "00000000-0000-0000-0000-000000000001"),
        ("reel_created", "Uploaded a reel", "reel", "00000000-0000-0000-0000-000000000002"),
        ("friend_added", "Became friends with Tech User", "profile", "00000000-0000-0000-0000-000000000003"),
        ("achievement_unlocked", "Unlocked '100 Followers' badge", "achievement", "00000000-0000-0000-0000-000000000004"),
        ("profile_viewed", "Profile visited by 50 people today", "metric", "00000000-0000-0000-0000-000000000005"),
    ]
    for atype, alabel, ttype, tid in data:
        write_query(
            "INSERT INTO chain_activity_log (profile_id, activity_type, activity_label, target_type, target_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (pid, atype, alabel, ttype, tid)
        )
    print(f"  ✓ activity seeded ({len(data)} entries)")


def seed_favorites(pid):
    music = ["Afrobeat Mix 2024", "Namibian Vibes", "Lo-Fi Beats", "Jazz Classics"]
    games = ["FIFA 24", "Call of Duty", "Minecraft", "GTA V"]
    for m in music:
        write_query(
            "INSERT INTO chain_user_favorites (profile_id, favorite_type, favorite_value, label) "
            "VALUES (%s, 'music', %s, %s) ON CONFLICT DO NOTHING",
            (pid, m, m)
        )
    for g in games:
        write_query(
            "INSERT INTO chain_user_favorites (profile_id, favorite_type, favorite_value, label) "
            "VALUES (%s, 'game', %s, %s) ON CONFLICT DO NOTHING",
            (pid, g, g)
        )
    print(f"  ✓ favorites seeded ({len(music) + len(games)} entries)")


def seed_timeline(pid):
    data = [
        ("joined", "Joined NamVibe", "🎉", "2024-01-15"),
        ("first_post", "First Post", "📷", "2024-02-01"),
        ("first_friend", "First Friend", "👥", "2024-02-15"),
        ("first_reel", "First Reel", "🎬", "2024-03-10"),
        ("verified", "Profile Verified", "✓", "2024-04-20"),
        ("followers_1k", "Reached 1K Followers", "🏆", "2024-06-01"),
        ("views_1m", "Reached 1M Views", "👁️", "2024-09-15"),
        ("creator_level", "Creator Level Up — Gold", "⭐", "2025-01-01"),
    ]
    for etype, elabel, eicon, edate in data:
        write_query(
            "INSERT INTO chain_profile_timeline (profile_id, event_type, event_label, event_icon, event_date) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (pid, etype, elabel, eicon, edate)
        )
    print(f"  ✓ timeline seeded ({len(data)} entries)")


def seed_achievements(pid):
    data = [
        ("first_post", "First Post", "📷", "#ec4899", "Posted your first photo on NamVibe"),
        ("followers_100", "100 Followers", "👥", "#f59e0b", "Reached 100 followers"),
        ("views_1m", "1 Million Views", "👁️", "#8b5cf6", "Your content reached 1 million views"),
        ("top_creator", "Top Creator", "⭐", "#ec4899", "Recognized as a top creator"),
        ("verified_artist", "Verified Artist", "🎨", "#10b981", "Verified as an artist on NamVibe"),
        ("health_hero", "Health Hero", "🏥", "#ef4444", "Promoted health awareness"),
        ("namvibe_legend", "NamVibe Legend", "👑", "#f59e0b", "Legendary status on the platform"),
        ("engagement_streak", "Engagement Streak", "🔥", "#f97316", "Active for 30 consecutive days"),
    ]
    for key, label, icon, color, desc in data:
        try:
            safe_insert("chain_achievements", {
                "profile_id": str(pid),
                "badge_key": key,
                "badge_label": label,
                "badge_icon": icon,
                "badge_color": color,
                "description": desc,
                "is_featured": key in ("namvibe_legend", "top_creator"),
            })
        except Exception:
            pass  # Table might be in Neon, not Supabase
    print(f"  ✓ achievements seeded ({len(data)} entries)")


def seed_badges(pid):
    data = [
        ("verified", "Verified", "✓", "#3b82f6"),
        ("premium", "Premium Member", "⭐", "#f59e0b"),
        ("creator", "Creator", "🎨", "#ec4899"),
        ("early_adopter", "Early Adopter", "🌅", "#8b5cf6"),
    ]
    for btype, blabel, bicon, bcolor in data:
        try:
            safe_insert("chain_profile_badges", {
                "profile_id": str(pid),
                "badge_type": btype,
                "badge_label": blabel,
                "badge_icon": bicon,
                "badge_color": bcolor,
                "is_visible": True,
            })
        except Exception:
            pass
    print(f"  ✓ badges seeded ({len(data)} entries)")


def seed_collections(pid):
    data = [
        ("Travel Memories", "Photos from my trips around Namibia", True, 1),
        ("Dev Life", "Code snippets and tech events", True, 2),
        ("Hidden Collection", "Personal favorites", False, 3),
    ]
    for title, desc, public, order in data:
        try:
            safe_insert("chain_collections", {
                "profile_id": str(pid),
                "title": title,
                "description": desc,
                "is_public": public,
                "sort_order": order,
            })
        except Exception:
            pass
    print(f"  ✓ collections seeded ({len(data)} entries)")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "alpha_user"
    print(f"\nSeeding premium profile data for: {target}")
    profile = get_profile(target)
    if not profile:
        print(f"✗ Profile '{target}' not found")
        return 1
    pid = profile["id"]
    print(f"  Profile: {profile.get('display_name')} ({pid})")
    update_profile_columns(pid)
    seed_education(pid)
    seed_work(pid)
    seed_skills(pid)
    seed_visitors(pid)
    seed_activity(pid)
    seed_favorites(pid)
    seed_timeline(pid)
    seed_achievements(pid)
    seed_badges(pid)
    seed_collections(pid)
    print(f"\n✅ Premium profile data seeded for {target}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
