#!/usr/bin/env python3
"""Seed initial support data: FAQ categories, articles, and a support agent for 'kaser'."""
import os
import sys

os.environ["CHAIN_DISABLE_DB_PING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.neon_service import execute, fetch_one, fetch_all
from services.logging_service import log_info, log_error


def seed_faq_categories():
    cats = [
        ("Getting Started", "getting-started", "Learn the basics of NamVibe", 1),
        ("Account & Profile", "account-profile", "Manage your account and profile settings", 2),
        ("Privacy & Safety", "privacy-safety", "Stay safe and control your privacy", 3),
        ("Payments & Wallet", "payments-wallet", "NVC coins, deposits, withdrawals, and billing", 4),
        ("Messaging & Calls", "messaging-calls", "Messages, voice and video calls", 5),
        ("Live Streaming", "live-streaming", "Go live, watch streams, gifts and tips", 6),
        ("Marketplace", "marketplace", "Buying and selling on NamVibe Marketplace", 7),
        ("Content & Creators", "content-creators", "Posts, reels, stories, and creator tools", 8),
        ("Verification", "verification", "Identity and creator verification", 9),
        ("Dating", "dating", "Dating features, safety, and matching", 10),
        ("Technical Issues", "technical-issues", "Bugs, errors, and troubleshooting", 11),
        ("Reports & Appeals", "reports-appeals", "Reporting content, appeals, and tickets", 12),
    ]
    for name, slug, desc, sort_order in cats:
        try:
            execute(
                "INSERT INTO chain_support_faq_categories (name, slug, description, sort_order) VALUES (%s,%s,%s,%s) ON CONFLICT (slug) DO NOTHING",
                (name, slug, desc, sort_order), timeout_ms=5000,
            )
            print(f"  OK: {slug}")
        except Exception as e:
            print(f"  ERR: {slug} - {e}")


def seed_articles():
    articles = [
        ("getting-started", "what-is-namvibe", "What is NamVibe?", "<p>NamVibe is a premium social platform connecting people through live streaming, messaging, dating, marketplace, and creative tools.</p>"),
        ("getting-started", "creating-your-account", "Creating Your Account", "<p>Sign up with email or phone. Verify your identity, set up your profile with a photo and bio, and start connecting.</p>"),
        ("account-profile", "editing-your-profile", "Editing Your Profile", "<p>Go to Settings &gt; Profile to update your display name, bio, avatar, cover photo, and personal details.</p>"),
        ("privacy-safety", "staying-safe-on-namvibe", "Staying Safe on NamVibe", "<p>Never share personal information. Use the Block and Report features. Enable two-factor authentication in Security settings.</p>"),
        ("payments-wallet", "nvc-coin-guide", "NVC Coin Guide", "<p>NVC coins are the platform currency. Earn by creating content, buy coins via wallet, send gifts in live streams, and tip creators.</p>"),
        ("messaging-calls", "sending-messages", "Sending Messages", "<p>Open a chat from a profile or the Messages tab. You can send text, images, voice messages, and start calls.</p>"),
        ("live-streaming", "going-live", "Going Live", "<p>Tap the + icon and select Go Live. Set your stream title, category, and go live. Viewers can send gifts and chat.</p>"),
        ("marketplace", "buying-on-marketplace", "Buying on Marketplace", "<p>Browse listings, contact sellers, arrange payment. Always use the platform for transactions. Report disputes to Support.</p>"),
        ("content-creators", "creating-a-post", "Creating a Post", "<p>Tap the + icon and select Post. Add your photo or video, write a caption, tag friends, and publish.</p>"),
        ("verification", "how-to-get-verified", "How to Get Verified", "<p>Go to Settings &gt; Verification and submit your ID. Verification helps build trust in the community.</p>"),
        ("technical-issues", "common-bug-fixes", "Common Bug Fixes", "<p>Try clearing your browser cache, updating the app, or restarting your device. If issues persist, create a support ticket.</p>"),
        ("reports-appeals", "how-to-report", "How to Report", "<p>Use the Report button on profiles, posts, or messages. Create a ticket in the Support Center for detailed reports.</p>"),
    ]
    for cat_slug, slug, title, content in articles:
        cat = fetch_one("SELECT id FROM chain_support_faq_categories WHERE slug=%s", (cat_slug,), timeout_ms=3000)
        if not cat:
            print(f"  SKIP (no category): {slug}")
            continue
        try:
            execute(
                "INSERT INTO chain_support_help_articles (category_id, title, slug, content, is_published) VALUES (%s,%s,%s,%s,TRUE) ON CONFLICT (slug) DO NOTHING",
                (cat["id"], title, slug, content), timeout_ms=5000,
            )
            print(f"  OK: {slug}")
        except Exception as e:
            print(f"  ERR: {slug} - {e}")


def seed_support_agent():
    profile = fetch_one("SELECT id FROM chain_profiles WHERE username='kaser'", timeout_ms=3000)
    if not profile:
        print("  SKIP: kaser profile not found")
        return
    try:
        execute(
            "INSERT INTO chain_support_agents (profile_id, display_name, role, is_active) VALUES (%s,'NamVibe Support','admin',TRUE) ON CONFLICT (profile_id) DO NOTHING",
            (profile["id"],), timeout_ms=5000,
        )
        print(f"  OK: support agent created for kaser (profile_id={profile['id']})")
    except Exception as e:
        print(f"  ERR: {e}")


def run_schema():
    sql_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql", "phase_support_tickets.sql")
    sql = open(sql_path).read()
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for stmt in statements:
        try:
            execute(stmt, timeout_ms=15000)
        except Exception as e:
            print(f"  SQL ERR: {e}")
    print("Schema applied.")


if __name__ == "__main__":
    print("=== Running Support Schema ===")
    run_schema()
    print("\n=== Seeding FAQ Categories ===")
    seed_faq_categories()
    print("\n=== Seeding Help Articles ===")
    seed_articles()
    print("\n=== Creating Support Agent ===")
    seed_support_agent()
    print("\nDone!")
