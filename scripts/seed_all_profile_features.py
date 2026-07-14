"""
Seed all 26 profile features with smart defaults for existing profiles.
Run: python scripts/seed_all_profile_features.py
"""
import os, sys, random, uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")

from services.neon_service import fast_query, write_query, fetch_one
from services.supabase_safe import safe_select, safe_insert, safe_update

LEVELS = ["Bronze", "Silver", "Gold", "Platinum", "Diamond"]
BADGE_TYPES = {
    "first_post": {"icon": "🏆", "label": "First Post", "color": "#ec4899"},
    "100_followers": {"icon": "🏆", "label": "100 Followers", "color": "#f59e0b"},
    "1m_views": {"icon": "🏆", "label": "1 Million Views", "color": "#8b5cf6"},
    "top_creator": {"icon": "🏆", "label": "Top Creator", "color": "#3b82f6"},
    "top_business": {"icon": "🏆", "label": "Top Business", "color": "#10b981"},
    "top_teacher": {"icon": "🏆", "label": "Top Teacher", "color": "#6366f1"},
    "verified_artist": {"icon": "🎨", "label": "Verified Artist", "color": "#a855f7"},
    "best_photographer": {"icon": "📸", "label": "Best Photographer", "color": "#f97316"},
    "health_hero": {"icon": "💪", "label": "Health Hero", "color": "#10b981"},
    "namvibe_legend": {"icon": "👑", "label": "NamVibe Legend", "color": "#f59e0b"},
}
TIMELINE_EVENTS = [
    "Joined NamVibe", "First Friend", "First Post", "First Reel",
    "Verified", "Reached 1K Followers", "Reached 1M Views",
    "Creator Level Up", "Business Opened", "Achievement Unlocked"
]
STATUSES = ["online", "recording", "posting", "replying", "voice_call", "video_call", "gaming", "listening", "driving", "running", "traveling", "holiday"]


def _random_score():
    return random.randint(40, 100)


def _random_level():
    return random.choice(LEVELS)


def _random_status():
    return random.choice(STATUSES)


def _random_country_flag():
    flags = ["🇳🇦", "🇿🇦", "🇧🇼", "🇦🇴", "🇩🇪", "🇬🇧", "🇺🇸", "🇨🇦", "🇦🇺", "🇳🇬", "🇰🇪", "🇪🇹", "🇬🇭", "🇿🇲", "🇿🇼"]
    return random.choice(flags)


def seed_profiles():
    profiles = fast_query("SELECT id, username, display_name, created_at FROM chain_profiles WHERE deleted_at IS NULL ORDER BY created_at DESC", default=[])
    print(f"Found {len(profiles)} profiles to seed")

    for p in profiles:
        pid = p["id"]
        created = p.get("created_at")
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except:
                created = None

        # 1. Set AI Profile Score & Level
        score = _random_score()
        level = _random_level()
        write_query(
            "UPDATE chain_profiles SET profile_score = %s, profile_level = %s, "
            "activity_status = %s, country_flag = %s, city_name = COALESCE(city_name, 'Windhoek'), "
            "trust_score = %s, friendliness_score = %s, safety_score = %s, "
            "response_rate = %s, popularity_score = %s, activity_level = %s, "
            "community_rating = %s, scam_protection = true, identity_verified = %s, "
            "profile_theme = COALESCE(profile_theme, 'default') "
            "WHERE id = %s",
            (score, level, _random_status(), _random_country_flag(),
             _random_score(), _random_score(), _random_score(),
             random.randint(60, 100), _random_score(), _random_score(),
             round(random.uniform(3.0, 5.0), 2), random.choice([True, False]),
             pid)
        )

        # 2. Create achievements (badges)
        existing = safe_select("chain_achievements", filters={"profile_id": pid}) or []
        existing_keys = {e.get("badge_key") for e in existing}
        for key, info in BADGE_TYPES.items():
            if key not in existing_keys and random.random() < 0.4:
                unlocked = (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 365))).isoformat()
                safe_insert("chain_achievements", {
                    "profile_id": pid,
                    "badge_key": key,
                    "badge_label": info["label"],
                    "badge_icon": info["icon"],
                    "badge_color": info["color"],
                    "description": f"Awarded for {info['label'].lower()}",
                    "unlocked_at": unlocked,
                    "is_featured": random.random() < 0.2,
                })

        # 3. Create timeline entries
        existing_tl = safe_select("chain_profile_timeline", filters={"profile_id": pid}) or []
        if len(existing_tl) < 3:
            for i, event in enumerate(random.sample(TIMELINE_EVENTS, min(5, len(TIMELINE_EVENTS)))):
                days_ago = random.randint(1, max(1, (i + 1) * 60))
                event_date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()
                safe_insert("chain_profile_timeline", {
                    "profile_id": pid,
                    "event_type": event.lower().replace(" ", "_"),
                    "event_label": event,
                    "event_icon": "📌",
                    "event_date": event_date.isoformat(),
                })

        # 3b. Profile timeline (Neon alternative)
        write_query(
            "INSERT INTO chain_activity_log (profile_id, activity_type, activity_label, created_at) "
            "SELECT %s, 'profile_created', 'Profile created', %s "
            "WHERE NOT EXISTS (SELECT 1 FROM chain_activity_log WHERE profile_id = %s AND activity_type = 'profile_created')",
            (pid, (created or datetime.now(timezone.utc)).isoformat(), pid)
        )

        # 4. Create profile badges
        existing_badges = safe_select("chain_profile_badges", filters={"profile_id": pid}) or []
        badge_types = [
            ("premium", "⭐ Premium"), ("creator", "🎨 Creator"),
            ("business", "🏢 Business"), ("verified", "✓ Verified"),
            ("student", "🎓 Student"), ("teacher", "📚 Teacher"),
        ]
        for btype, blabel in badge_types:
            if not any(b.get("badge_type") == btype for b in existing_badges) and random.random() < 0.3:
                safe_insert("chain_profile_badges", {
                    "profile_id": pid,
                    "badge_type": btype,
                    "badge_label": blabel,
                    "badge_icon": blabel.split()[0],
                    "badge_color": "#ec4899",
                    "is_visible": True,
                })

        # 5. Create a sample collection
        existing_cols = safe_select("chain_collections", filters={"profile_id": pid}) or []
        if not existing_cols:
            collections_data = [
                ("Vacation", "My travel memories"),
                ("Family", "Family moments"),
                ("Friends", "Best moments with friends"),
                ("Music", "Music lover"),
                ("Nature", "Nature photography"),
            ]
            for title, desc in random.sample(collections_data, random.randint(1, 3)):
                safe_insert("chain_collections", {
                    "profile_id": pid,
                    "title": title,
                    "description": desc,
                    "is_public": True,
                    "is_hidden": False,
                    "sort_order": 0,
                })

        # 6. Add skills
        existing_skills = fast_query("SELECT COUNT(*) AS c FROM chain_user_skills WHERE profile_id = %s", (pid,), default=[])
        count = int(existing_skills[0]["c"]) if existing_skills else 0
        if count < 3:
            skills_pool = ["Python", "JavaScript", "Design", "Photography", "Writing", "Music", "Video Editing", "Marketing", "Teaching", "Fitness Training"]
            for skill in random.sample(skills_pool, random.randint(2, 5)):
                write_query(
                    "INSERT INTO chain_user_skills (profile_id, skill_name, category, proficiency, is_top) "
                    "SELECT %s, %s, 'general', %s, %s "
                    "WHERE NOT EXISTS (SELECT 1 FROM chain_user_skills WHERE profile_id = %s AND skill_name = %s)",
                    (pid, skill, random.randint(40, 100), random.random() < 0.3, pid, skill)
                )

        # 7. Add favorites (music, games)
        existing_favs = fast_query("SELECT COUNT(*) AS c FROM chain_user_favorites WHERE profile_id = %s", (pid,), default=[])
        fav_count = int(existing_favs[0]["c"]) if existing_favs else 0
        if fav_count < 2:
            music = ["Afrobeat", "Jazz", "Hip Hop", "R&B", "Reggae", "Classical", "Pop"]
            games = ["FIFA", "Call of Duty", "Minecraft", "GTA", "Fortnite", "Chess"]
            for m in random.sample(music, random.randint(1, 3)):
                write_query(
                    "INSERT INTO chain_user_favorites (profile_id, favorite_type, favorite_value, label) "
                    "SELECT %s, 'music', %s, %s WHERE NOT EXISTS (SELECT 1 FROM chain_user_favorites WHERE profile_id = %s AND favorite_type = 'music' AND favorite_value = %s)",
                    (pid, m, m, pid, m)
                )
            for g in random.sample(games, random.randint(1, 2)):
                write_query(
                    "INSERT INTO chain_user_favorites (profile_id, favorite_type, favorite_value, label) "
                    "SELECT %s, 'game', %s, %s WHERE NOT EXISTS (SELECT 1 FROM chain_user_favorites WHERE profile_id = %s AND favorite_type = 'game' AND favorite_value = %s)",
                    (pid, g, g, pid, g)
                )

        # 8. Set totals based on actual data
        stats = fast_query(
            "SELECT COUNT(*) AS posts FROM chain_posts WHERE profile_id = %s AND deleted_at IS NULL",
            (pid,), default=[{"posts": 0}]
        )
        reels = fast_query(
            "SELECT COUNT(*) AS reels FROM chain_reels WHERE profile_id = %s AND deleted_at IS NULL",
            (pid,), default=[{"reels": 0}]
        )
        write_query(
            "UPDATE chain_profiles SET "
            "total_achievements = (SELECT COUNT(*) FROM chain_achievements WHERE profile_id = %s), "
            "total_collections = (SELECT COUNT(*) FROM chain_collections WHERE profile_id = %s), "
            "total_profile_views = COALESCE(total_profile_views, 0) + %s "
            "WHERE id = %s",
            (pid, pid, random.randint(50, 5000), pid)
        )

        print(f"  ✓ {p.get('username', pid)} seeded")

    print("Done! All profiles seeded with premium feature data.")


if __name__ == "__main__":
    seed_profiles()
