# NVC (NamVibeCoin) Economy — Central Pricing Configuration
# 1 NVC = 5 NAD (Namibian Dollars)

COIN_VALUE_NAD = 5

# ── Coin Packs ───────────────────────────────────────────
COIN_PACKS = [
    {"id": "starter",  "name": "Starter",  "coins": 10,   "price_nad": 50,    "bonus": 0},
    {"id": "bronze",   "name": "Bronze",   "coins": 25,   "price_nad": 125,   "bonus": 0},
    {"id": "silver",   "name": "Silver",   "coins": 50,   "price_nad": 250,   "bonus": 0},
    {"id": "gold",     "name": "Gold",     "coins": 100,  "price_nad": 500,   "bonus": 0},
    {"id": "platinum", "name": "Platinum", "coins": 250,  "price_nad": 1250,  "bonus": 0},
    {"id": "diamond",  "name": "Diamond",  "coins": 500,  "price_nad": 2500,  "bonus": 25},
    {"id": "elite",    "name": "Elite",    "coins": 1000, "price_nad": 5000,  "bonus": 50},
]

# ── Membership Tiers (paid in NVC) ───────────────────────
MEMBERSHIP_TIERS = {
    "free":           {"label": "Free",           "monthly": 0,   "yearly": 0,    "nad_monthly": 0},
    "plus":           {"label": "Plus",           "monthly": 5,   "yearly": 50,   "nad_monthly": 25},
    "pro":            {"label": "Pro",            "monthly": 10,  "yearly": 100,  "nad_monthly": 50},
    "premium":        {"label": "Premium",        "monthly": 20,  "yearly": 200,  "nad_monthly": 100},
    "creator_elite":  {"label": "Creator Elite",  "monthly": 40,  "yearly": 400,  "nad_monthly": 200},
    "business":       {"label": "Business",       "monthly": 60,  "yearly": 600,  "nad_monthly": 300},
    "enterprise":     {"label": "Enterprise",     "monthly": None,"yearly": None, "nad_monthly": None},
}

# ── Profile Themes (one-time NVC) ────────────────────────
PROFILE_THEMES = [
    {"id": "basic",       "name": "Basic Theme",     "coins": 2,   "nad": 10},
    {"id": "neon",        "name": "Neon Theme",      "coins": 5,   "nad": 25},
    {"id": "royal_gold",  "name": "Royal Gold",      "coins": 10,  "nad": 50},
    {"id": "galaxy",      "name": "Galaxy Theme",    "coins": 15,  "nad": 75},
    {"id": "diamond",     "name": "Diamond Theme",   "coins": 25,  "nad": 125},
]

# ── Verification Fees (NVC) ──────────────────────────────
VERIFICATION_FEES = {
    "blue":       {"label": "Blue Verification",       "coins": 20,  "nad": 100},
    "business":   {"label": "Business Verification",   "coins": 40,  "nad": 200},
    "government": {"label": "Government Verification", "coins": 0,   "nad": 0,    "note": "Free after approval"},
    "ngo":        {"label": "NGO Verification",        "coins": 15,  "nad": 75},
}

# ── Creator Subscription Tiers (paid by fans in NVC/month) ─
CREATOR_SUBSCRIPTION_TIERS = [
    {"id": "bronze_fan", "name": "Bronze Fan", "coins": 5,   "nad": 25},
    {"id": "silver_fan", "name": "Silver Fan", "coins": 10,  "nad": 50},
    {"id": "gold_fan",   "name": "Gold Fan",   "coins": 20,  "nad": 100},
    {"id": "vip_fan",    "name": "VIP Fan",    "coins": 50,  "nad": 250},
]

# ── Live Stream Gifts ────────────────────────────────────
LIVE_GIFTS = [
    {"id": "heart",  "name": "Heart",  "emoji": "❤️",  "coins": 1,    "nad": 5},
    {"id": "rose",   "name": "Rose",   "emoji": "🌹",  "coins": 2,    "nad": 10},
    {"id": "coffee", "name": "Coffee", "emoji": "☕",  "coins": 3,    "nad": 15},
    {"id": "pizza",  "name": "Pizza",  "emoji": "🍕",  "coins": 5,    "nad": 25},
    {"id": "cake",   "name": "Cake",   "emoji": "🎂",  "coins": 10,   "nad": 50},
    {"id": "diamond","name": "Diamond","emoji": "💎",  "coins": 20,   "nad": 100},
    {"id": "car",    "name": "Car",    "emoji": "🚗",  "coins": 100,  "nad": 500},
    {"id": "jet",    "name": "Jet",    "emoji": "✈️",  "coins": 500,  "nad": 2500},
    {"id": "crown",  "name": "Crown",  "emoji": "👑",  "coins": 1000, "nad": 5000},
]

# ── Marketplace Commission Rates ─────────────────────────
MARKETPLACE_COMMISSION = {
    "standard_seller": 0.05,
    "premium_seller":  0.03,
    "business_seller": 0.02,
}

# ── Advertising Costs (NVC/day) ──────────────────────────
ADVERTISING = [
    {"id": "boost_post",         "name": "Boost Post",         "coins": 5,   "nad": 25},
    {"id": "boost_reel",         "name": "Boost Reel",         "coins": 10,  "nad": 50},
    {"id": "homepage_promo",     "name": "Homepage Promotion", "coins": 20,  "nad": 100},
    {"id": "trending_placement", "name": "Trending Placement", "coins": 50,  "nad": 250},
]

# ── Extra Storage (NVC/month) ────────────────────────────
EXTRA_STORAGE = [
    {"id": "50gb",  "name": "50 GB",  "coins": 5,   "nad": 25},
    {"id": "200gb", "name": "200 GB", "coins": 10,  "nad": 50},
    {"id": "1tb",   "name": "1 TB",   "coins": 20,  "nad": 100},
]

# ── Earning Methods (informational) ──────────────────────
EARNING_METHODS = [
    {"id": "daily_login",         "name": "Daily Login Rewards",        "description": "Log in daily to earn bonus NVC"},
    {"id": "referral",            "name": "Referral Bonuses",           "description": "Invite friends and earn NVC when they join"},
    {"id": "profile_completion",  "name": "Completing Profile",         "description": "Fill in your profile details to earn NVC"},
    {"id": "content_posting",     "name": "Posting Quality Content",    "description": "Earn NVC when your posts get engagement"},
    {"id": "viral_reels",         "name": "Viral Reels",                "description": "Viral reels earn bonus NVC payouts"},
    {"id": "receiving_gifts",     "name": "Receiving Gifts",            "description": "Gifts from fans convert to NVC"},
    {"id": "competitions",        "name": "Winning Competitions",       "description": "Compete and win NVC prizes"},
    {"id": "marketplace_sales",   "name": "Marketplace Sales",          "description": "Sell items and earn NVC"},
    {"id": "business_referrals",  "name": "Business Referrals",         "description": "Refer businesses to NamVibe and earn"},
    {"id": "challenges",          "name": "Official NamVibe Challenges", "description": "Participate in platform challenges for NVC rewards"},
]

# ── Revenue Streams (informational) ──────────────────────
REVENUE_STREAMS = [
    {"name": "NVC Coin Purchases",         "description": "Users buy coin packs with real money"},
    {"name": "Membership Subscriptions",   "description": "Monthly/yearly tier memberships"},
    {"name": "Creator Subscriptions",      "description": "Fan subscriptions to creators"},
    {"name": "Marketplace Commissions",    "description": "Percentage fee on marketplace sales"},
    {"name": "Advertising",                "description": "Boosted posts and promoted placements"},
    {"name": "Live Stream Gifts",          "description": "Platform cut of live gifts"},
    {"name": "Creator Tipping",            "description": "Platform fee on tips"},
    {"name": "Business Subscriptions",     "description": "Business accounts pay for features"},
    {"name": "Verification Services",      "description": "Application fees for blue/business verification"},
    {"name": "Premium Profile Themes",     "description": "One-time purchase profile themes"},
    {"name": "Cloud Storage Upgrades",     "description": "Extra storage monthly subscription"},
    {"name": "AI-Powered Premium Features","description": "AI tools and insights subscription"},
]


def coins_to_nad(coins: int) -> int:
    return coins * COIN_VALUE_NAD


def nad_to_coins(nad: int) -> int:
    return max(1, nad // COIN_VALUE_NAD)


def get_coin_pack(pack_id: str) -> dict | None:
    for p in COIN_PACKS:
        if p["id"] == pack_id:
            return dict(p)
    return None


def get_membership_tier(tier_id: str) -> dict | None:
    return MEMBERSHIP_TIERS.get(tier_id)


def get_verification_fee(verification_type: str) -> dict | None:
    return VERIFICATION_FEES.get(verification_type)


def get_live_gift(gift_id: str) -> dict | None:
    for g in LIVE_GIFTS:
        if g["id"] == gift_id:
            return dict(g)
    return None


def get_commission_rate(seller_type: str = "standard_seller") -> float:
    return MARKETPLACE_COMMISSION.get(seller_type, 0.05)
