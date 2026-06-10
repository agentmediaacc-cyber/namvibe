#!/usr/bin/env python3
"""Phase 64 — Seed premium live streaming data for demo users."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"

from services.neon_service import write_query, fast_query
from services.supabase_safe import safe_insert, safe_select

SEED_PROFILES = ["chain_star", "chain_moon", "chain_gold", "chain_million", "chain_premium"]

GIFT_CATALOG = [
    {"gift_name": "Heart", "gift_icon": "❤️", "coin_price": 10, "tier": "standard", "sort_order": 1},
    {"gift_name": "Rose", "gift_icon": "🌹", "coin_price": 25, "tier": "standard", "sort_order": 2},
    {"gift_name": "Crown", "gift_icon": "👑", "coin_price": 50, "tier": "standard", "sort_order": 3},
    {"gift_name": "Diamond Ring", "gift_icon": "💍", "coin_price": 100, "tier": "premium", "sort_order": 4},
    {"gift_name": "Luxury Car", "gift_icon": "🚗", "coin_price": 250, "tier": "premium", "sort_order": 5},
    {"gift_name": "Castle", "gift_icon": "🏰", "coin_price": 500, "tier": "luxury", "sort_order": 6},
    {"gift_name": "Rocket Ship", "gift_icon": "🚀", "coin_price": 1000, "tier": "luxury", "sort_order": 7},
    {"gift_name": "Galaxy", "gift_icon": "🌌", "coin_price": 2500, "tier": "legendary", "sort_order": 8},
]

def seed_gift_catalog():
    existing = safe_select("chain_gift_catalog", limit=1)
    if existing:
        print("  Gift catalog already seeded, skipping.")
        return
    for g in GIFT_CATALOG:
        safe_insert("chain_gift_catalog", g)
        print(f"  Added gift: {g['gift_name']} ({g['coin_price']} coins, {g['tier']})")

def seed_rooms_and_participants():
    profiles = safe_select("chain_profiles", limit=20, filters={"username": ("in", SEED_PROFILES)})
    username_map = {p["username"]: p for p in profiles}

    room_data = [
        {"title": "Star Music Session", "host": "chain_star", "category": "Music", "is_live": True, "access_type": "public"},
        {"title": "Moon Art Studio", "host": "chain_moon", "category": "Education", "is_live": True, "access_type": "public"},
        {"title": "Gold Premium Lounge", "host": "chain_gold", "category": "Lifestyle", "is_live": True, "access_type": "premium"},
        {"title": "Million Business Talk", "host": "chain_million", "category": "Business", "is_live": True, "access_type": "public"},
        {"title": "Premium VIP Stream", "host": "chain_premium", "category": "Entertainment", "is_live": True, "access_type": "premium"},
    ]

    for rd in room_data:
        host = username_map.get(rd["host"])
        if not host:
            print(f"  Skipping room '{rd['title']}': host {rd['host']} not found")
            continue
        existing_rooms = safe_select("chain_live_rooms", filters={"title": rd["title"], "host_profile_id": host["id"]}, limit=1, order_by=None)
        if existing_rooms:
            print(f"  Room '{rd['title']}' already exists, skipping.")
            continue
        room = safe_insert("chain_live_rooms", {
            "profile_id": host["id"],
            "host_profile_id": host["id"],
            "title": rd["title"],
            "host_name": host.get("full_name") or rd["host"],
            "category": rd["category"],
            "status": "live",
            "is_live": True,
            "access_type": rd["access_type"],
            "viewer_count": 0,
            "gift_total": 0,
            "gift_total_earned": 0,
            "allow_comments": True,
            "allow_gifts": True,
            "created_at": "2026-06-10T12:00:00Z",
        })
        if room:
            safe_insert("chain_live_participants", {"room_id": room[0]["id"], "profile_id": host["id"], "role": "host", "is_active": True})
            # Seed some goals
            safe_insert("chain_live_goals", {"room_id": room[0]["id"], "title": "Reach 500 gift coins", "target_amount": 500, "current_amount": 120, "goal_type": "gifts", "is_active": True})
            safe_insert("chain_live_goals", {"room_id": room[0]["id"], "title": "Get 50 viewers", "target_amount": 50, "current_amount": 12, "goal_type": "viewers", "is_active": True})
            # Seed some earnings
            safe_insert("chain_live_earnings", {"profile_id": host["id"], "room_id": room[0]["id"], "source_type": "gift", "amount": 250, "currency": "coins", "status": "available"})
            safe_insert("chain_live_earnings", {"profile_id": host["id"], "room_id": room[0]["id"], "source_type": "tip", "amount": 75, "currency": "coins", "status": "pending"})
            print(f"  Created room: '{rd['title']}' with goals and earnings")

    # Seed cross-room raids
    rooms = safe_select("chain_live_rooms", limit=5, order_by="created_at", desc=True)
    if len(rooms) >= 2:
        existing_raids = safe_select("chain_live_raids", limit=1)
        if not existing_raids:
            safe_insert("chain_live_raids", {"source_room_id": rooms[0]["id"], "target_room_id": rooms[1]["id"], "host_profile_id": rooms[0]["host_profile_id"], "viewer_count": 15, "status": "completed"})
            print("  Seeded 1 raid")

if __name__ == "__main__":
    print("Seeding Phase 64 — Premium Live Streaming...")
    seed_gift_catalog()
    seed_rooms_and_participants()
    print("Done seeding Phase 64.")
