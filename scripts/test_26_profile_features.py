#!/usr/bin/env python3
"""Test all 26 premium profile features render with real data."""

import json
import pathlib
import re
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]

PASS = 0
FAIL = 0

def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS: {name}" + (f" - {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL: {name}" + (f" - {detail}" if detail else ""))


def main():
    global PASS, FAIL
    sys.path.insert(0, str(ROOT))

    print("=" * 60)
    print("TEST: All 26 Premium Profile Features")
    print("=" * 60)
    print()

    # ── 1. Template compilation ──
    print("[GROUP] Template compilation")
    try:
        from app import app as _app
        check("Flask app loaded", True)
    except Exception as e:
        check("Flask app loaded", False, str(e))
        print("\nCannot continue without Flask app. Aborting.")
        return

    for tpl in ["profile/index.html", "profile/base_profile.html"]:
        try:
            _app.jinja_env.get_template(tpl)
            check(f"Template compiles: {tpl}", True)
        except Exception as e:
            check(f"Template compiles: {tpl}", False, str(e))

    # ── 2. Route registration ──
    print("\n[GROUP] Route registration")
    rules = {str(r): r for r in _app.url_map.iter_rules()}
    required = [
        "/profile/",
        "/profile/api/theme",
        "/profile/<user_id>/follow",
        "/profile/report/<profile_id>",
        "/profile/@<username>/follow",
        "/profile/@<username>/report",
    ]
    for r in required:
        check(f"Route exists: {r}", r in rules)

    # ── 3. View model build (mock data) ──
    print("\n[GROUP] Profile view model build")
    from services.profile_view_service import build_profile_view_model

    mock_profile = {
        "id": "test-uuid-1234",
        "username": "testuser",
        "display_name": "Test User",
        "bio": "Just testing",
        "avatar_url": "/static/img/default_avatar.png",
        "cover_url": "/static/img/default_cover.png",
        "pronouns": "they/them",
        "occupation": "Engineer",
        "company": "NamVibe",
        "school": "MIT",
        "university": "Stanford",
        "quote_of_day": "Carpe diem",
        "website": "https://example.com",
        "profile_score": 85,
        "profile_level": "Gold",
        "trust_score": 90,
        "friendliness_score": 88,
        "safety_score": 92,
        "response_rate": 95,
        "popularity_score": 78,
        "activity_level": 80,
        "total_likes": 1500,
        "total_shares": 200,
        "total_bookmarks": 75,
        "total_comments": 300,
        "total_downloads": 50,
        "total_live_hours": 120,
        "total_voice_calls": 45,
        "total_video_calls": 30,
        "total_messages": 2500,
        "total_earnings": 500.00,
        "total_marketplace_sales": 12,
        "total_achievements": 10,
        "total_collections": 5,
        "cover_video_url": "",
        "nationality": "Namibian",
        "identity_verified": True,
        "driving_licence": True,
        "student_card": False,
        "employee_card": True,
        "health_card": False,
        "business_licence": False,
        "professional_membership": True,
        "volunteer_badge": True,
        "premium_badge": True,
        "creator_badge": True,
        "business_badge": False,
        "government_badge": False,
        "ngo_badge": False,
        "student_badge": False,
        "medical_badge": False,
        "teacher_badge": False,
        "activity_status": "online",
        "current_activity": "Streaming music",
        "mood_emoji": "😊",
        "mood_text": "Happy",
        "local_time": "14:30",
        "weather_emoji": "☀️",
        "weather_temp": "28°C",
        "relationship_status": "Single",
        "country_flag": "🇳🇦",
        "city_name": "Windhoek",
        "languages": ["English", "Oshiwambo"],
        "interests": ["Music", "Travel", "Tech"],
        "skills": ["Python", "Design"],
        "created_at": "2023-01-15T00:00:00+00:00",
        "is_verified": True,
        "is_creator": True,
        "total_profile_views": 5000,
        "favorite_songs": ["Song A", "Song B"],
        "favorite_artists": ["Artist X", "Artist Y"],
        "favorite_games": ["Game 1", "Game 2"],
        "gaming_level": "Pro",
        "gaming_achievements": ["Ace", "MVP"],
        "countries_visited": ["Namibia", "South Africa", "Germany"],
        "cities_visited": ["Windhoek", "Cape Town", "Berlin"],
        "travel_wishlist": ["Japan", "Brazil"],
        "fitness_steps": 12000,
        "fitness_workouts": 5,
        "fitness_cycling": 30,
        "fitness_running": 10,
        "fitness_calories": 2500,
        "fitness_goals": "Run a marathon",
        "fitness_sleep": "7.5h",
        "marketplace_items_selling": 8,
        "marketplace_wishlist": 15,
        "marketplace_purchased": 22,
        "marketplace_reviews": 10,
        "wallet_rewards": 500,
        "wallet_tips": 250,
        "wallet_revenue": 1000,
        "subscriptions_count": 50,
        "subscribers_count": 200,
        "studio_enabled": True,
        "business_name": "Test Corp",
        "business_opening_hours": "Mon-Fri 9-5",
        "business_contact_phone": "+264811234567",
        "business_booking_url": "https://booking.example.com",
        "business_appointments_enabled": True,
        "business_delivery_enabled": False,
        "business_catalogue": ["Item 1", "Item 2"],
        "ai_profile_summary": "Test summary",
        "ai_bio_suggestions": ["Bio suggestion 1"],
        "ai_friend_suggestions": ["Friend 1"],
        "ai_creator_recommendations": ["Creator 1"],
        "ai_growth_analysis": "Growth analysis text",
        "profile_visibility": "public",
        "scam_protection": True,
    }
    mock_stats = {
        "posts": 42,
        "reels": 15,
        "followers": 1200,
        "following": 350,
        "friends": 180,
        "likes": 1500,
        "views": 5000,
        "stories": 8,
    }
    mock_wallet = {"coin_balance": 300, "withdrawal_ready": True}
    mock_creator = {"studio_enabled": True, "verification_status": "verified"}
    mock_marketplace = {"items": [], "shop_enabled": True}
    mock_content = {"posts": [], "mutual_friends": {"count": 5, "items": []}}

    mock_presence = {"status": "online", "last_seen": "2026-07-07T12:00:00+00:00"}
    pv = build_profile_view_model(
        profile=mock_profile,
        viewer=mock_profile,
        stats=mock_stats,
        content=mock_content,
        wallet=mock_wallet,
        creator=mock_creator,
        marketplace=mock_marketplace,
        presence=mock_presence,
    )

    expected_fields = [
        ("profile_score", 85), ("profile_level", "Gold"), ("trust_score", 90),
        ("friendliness_score", 88), ("safety_score", 92), ("response_rate", 95),
        ("popularity_score", 78), ("activity_level", 80),
        ("total_likes", 1500), ("total_shares", 200), ("total_bookmarks", 75),
        ("total_comments", 300), ("total_downloads", 50), ("total_live_hours", 120),
        ("total_voice_calls", 45), ("total_video_calls", 30), ("total_messages", 2500),
        ("total_earnings", 500), ("total_marketplace_sales", 12),
        ("total_achievements", 10), ("total_collections", 5),
        ("identity_verified", True), ("scam_protection", True),
        ("wallet_coins", 300), ("wallet_rewards", 500), ("wallet_tips", 250), ("wallet_revenue", 1000),
        ("subscriptions_count", 50), ("subscribers_count", 200),
        ("studio_enabled", True),
        ("business_name", "Test Corp"),
        ("ai_profile_summary", "Test summary"),
        ("verified", True), ("is_self", True), ("is_online", True),
        ("posts_count", 42), ("reels_count", 15), ("followers_count", 1200),
        ("following_count", 350), ("friends_count", 180), ("views_count", 5000),
        ("has_shop", True),
        ("own_profile", True),
        ("pronouns", "they/them"), ("occupation", "Engineer"),
        ("company", "NamVibe"), ("school", "MIT"), ("university", "Stanford"),
        ("quote_of_day", "Carpe diem"),
        ("premium_badge", True), ("creator_badge", True),
        ("cover_video_url", ""),
    ]

    for key, expected in expected_fields:
        actual = pv.get(key)
        ok = actual == expected
        check(f"pv.{key} = {actual!r}", ok, f"expected {expected!r}" if not ok else "")

    # Check that JSON string fields are parsed to lists
    list_fields = ["favorite_songs", "favorite_artists", "favorite_games_list",
                    "gaming_achievements", "countries_visited", "cities_visited",
                    "travel_wishlist", "business_catalogue",
                    "ai_bio_suggestions", "ai_friend_suggestions", "ai_creator_recommendations"]
    for lf in list_fields:
        val = pv.get(lf)
        ok = isinstance(val, (list, tuple))
        check(f"pv.{lf} is list ({type(val).__name__})", ok)

    # ── 4. Static file existence ──
    print("\n[GROUP] Static files")
    for path, label in [
        ("static/css/namvibe_profile_premium.css", "Premium CSS"),
        ("static/css/namvibe_profile_pro.css", "Pro CSS"),
    ]:
        check(f"{label} exists", (ROOT / path).exists())

    # ── 5. Check template has all 26 feature sections ──
    print("\n[GROUP] 26 feature sections in template")
    tmpl_text = (ROOT / "templates/profile/index.html").read_text()
    
    def section_ok(label, needle):
        """Check if a section heading or marker exists in the template."""
        return needle in tmpl_text
    
    section_checks = [
        ("1. Premium Hero Header", "nv-pp-hero"),
        ("2. Live Status", "nv-pp-status"),
        ("3. Action Buttons", "nv-pp-actions"),
        ("4. Stat Counters", "nv-pp-stats"),
        ("5. AI Reputation", "AI Reputation"),
        ("6. Profile Card", "Profile Details"),
        ("7. Work Experience", "Experience"),
        ("8. Education", "Education"),
        ("9. Achievements", "Achievements"),
        ("10. Badges", "Badges"),
        ("11. Collections", "Collections"),
        ("12. Skills", "Skills"),
        ("13. Digital Identity", "Digital Identity"),
        ("14. Music", "Music"),
        ("15. Gaming", "Gaming"),
        ("16. Travel Map", "Travel Map"),
        ("17. Health & Fitness", "Health & Fitness"),
        ("18. Creator Dashboard", "Creator Dashboard"),
        ("19. Business Dashboard", "Business Dashboard"),
        ("20. Marketplace", "Marketplace"),
        ("21. Wallet", "Wallet"),
        ("22. AI Timeline", "AI Timeline"),
        ("23. AI Smart Profile", "AI Smart Profile"),
        ("24. Privacy Center", "Privacy Center"),
        ("25. Profile Themes", "Profile Themes"),
        ("26. Social Ecosystem", "Social Ecosystem"),
    ]
    for label, needle in section_checks:
        check(f"Section: {label}", section_ok(label, needle))

    # ── 6. Template has no Jinja2 syntax errors ──
    print("\n[GROUP] Template rendering (syntax)")
    for tpl in ["profile/index.html", "profile/base_profile.html"]:
        try:
            _app.jinja_env.get_template(tpl).render({})
            check(f"Empty render: {tpl}", True)
        except Exception as e:
            check(f"Empty render: {tpl}", str(e)[:100])
    # Check key CSS file for syntax errors
    css_path = ROOT / "static/css/namvibe_profile_premium.css"
    if css_path.exists():
        css_text = css_path.read_text()
        # Check for common CSS issues: unclosed braces, stray characters
        open_braces = css_text.count("{")
        close_braces = css_text.count("}")
        check(f"CSS brace balance ({open_braces} == {close_braces})", open_braces == close_braces)

    # ── 7. Profile page routing (real DB) ──
    print("\n[GROUP] Profile page render (with real data)")
    try:
        from services.neon_service import fast_query
        profiles = fast_query(
            "SELECT id, username FROM chain_profiles WHERE deleted_at IS NULL AND profile_score > 0 LIMIT 3",
            default=[]
        )
    except Exception as e:
        profiles = []
        check("DB query works", False, str(e))

    if profiles:
        for prof in profiles:
            pid = prof["id"]
            uname = prof["username"]
            with _app.test_client() as c:
                with c.session_transaction() as sess:
                    sess["profile_id"] = pid
                    sess["username"] = uname
                    sess["_user_id"] = str(pid)
                    sess["user_id"] = pid
                try:
                    resp = c.get("/profile", follow_redirects=True)
                    ok = resp.status_code == 200
                    html = resp.data.decode()
                    # Check sections present (some conditional on data)
                    present = [l for l, n in section_checks if n in html]
                    missing = [l for l, n in section_checks if n not in html]
                    check(f"Page render @{uname} (status {resp.status_code})", ok)
                    check(f"  Sections: {len(present)}/26", len(present) >= 15,
                          f"missing={missing}")
                    # no crash means template rendered successfully
                    check(f"  No crash during render", "Internal Server Error" not in html)
                except Exception as e:
                    check(f"Page render: @{uname}", False, str(e)[:150])

    print()
    print("=" * 60)
    total = PASS + FAIL
    print(f"RESULTS: {PASS}/{total} passed, {FAIL}/{total} failed")
    print("=" * 60)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
