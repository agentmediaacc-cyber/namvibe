#!/usr/bin/env python3
"""Phase 34 — Creator Dashboard Feature Test"""

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} {detail}")
        failed += 1

# 1. Routes exist
try:
    from api_routes.creator_routes import creator_bp
    check("creator_routes blueprint exists", True)
except Exception as e:
    check("creator_routes blueprint exists", False, str(e))

try:
    from api_routes.dashboard_routes import dashboard_bp
    check("dashboard_routes blueprint exists", True)
except Exception as e:
    check("dashboard_routes blueprint exists", False, str(e))

# Check route content
try:
    creator_content = open(os.path.join(BASE, "api_routes", "creator_routes.py")).read()
    creator_endpoints = [
        ("dashboard", "/creator/dashboard"),
        ("verification_request", "/creator/verification/request"),
        ("api_subscription", "/creator/subscriptions"),
        ("api_paid_post", "/creator/paid-posts"),
        ("api_premium_content", "/creator/premium-content"),
        ("api_payout", "/creator/payouts"),
        ("api_gift_conversion", "/creator/gift-conversions"),
        ("api_revenue_report", "/creator/revenue-reports"),
        ("api_sponsorship", "/creator/sponsorships"),
        ("api_creator_badge", "/creator/badges"),
        ("api_supporter_badge", "/creator/supporter-badges"),
        ("api_top_fan", "/creator/top-fans"),
        ("api_ranking", "/creator/rankings"),
    ]
    for func, route in creator_endpoints:
        check(f"Route: {func} -> {route}", func in creator_content, f"{func} not found in creator_routes.py")
except Exception as e:
    check("creator_routes.py readable", False, str(e))

# 2. Services exist
try:
    from services.creator_feature_service import (
        creator_dashboard, request_verification,
        create_subscription, create_paid_post, create_premium_content,
        request_payout, record_gift_conversion, create_revenue_report,
        create_sponsorship, award_creator_badge, award_supporter_badge,
        upsert_top_fan, upsert_creator_ranking,
        get_subscriptions, get_paid_posts, get_premium_content,
        get_sponsorships, get_creator_badges,
    )
    check("creator_feature_service: creator_dashboard", callable(creator_dashboard))
    check("creator_feature_service: request_verification", callable(request_verification))
    check("creator_feature_service: create_subscription", callable(create_subscription))
    check("creator_feature_service: create_paid_post", callable(create_paid_post))
    check("creator_feature_service: create_premium_content", callable(create_premium_content))
    check("creator_feature_service: request_payout", callable(request_payout))
    check("creator_feature_service: create_sponsorship", callable(create_sponsorship))
    check("creator_feature_service: award_creator_badge", callable(award_creator_badge))
    check("creator_feature_service: upsert_top_fan", callable(upsert_top_fan))
    check("creator_feature_service: get_subscriptions", callable(get_subscriptions))
    check("creator_feature_service: get_paid_posts", callable(get_paid_posts))
    check("creator_feature_service: get_premium_content", callable(get_premium_content))
    check("creator_feature_service: get_sponsorships", callable(get_sponsorships))
    check("creator_feature_service: get_creator_badges", callable(get_creator_badges))
except Exception as e:
    check("creator_feature_service imports", False, str(e))

try:
    from services.profile_dashboard_service import build_profile_dashboard
    check("profile_dashboard_service: build_profile_dashboard", callable(build_profile_dashboard))
except Exception as e:
    check("profile_dashboard_service import", False, str(e))

# 3. Templates exist
templates = [
    "templates/creator/dashboard.html",
    "templates/dashboard/complete_dashboard.html",
    "templates/dashboard/index.html",
    "templates/dashboard/feature_page.html",
    "templates/dashboard/legal.html",
]
for t in templates:
    check(f"Template {t} exists", os.path.exists(os.path.join(BASE, t)))

# 4. DB tables in SQL
sql_files = []
for root, dirs, files in os.walk(os.path.join(BASE, "sql")):
    for f in files:
        if f.endswith(".sql"):
            sql_files.append(os.path.join(root, f))

all_sql = ""
for sf in sql_files:
    with open(sf) as fh:
        all_sql += fh.read()

creator_tables = [
    "chain_creator_subscriptions", "chain_creator_earnings",
    "chain_creator_supporters", "chain_creator_paid_posts",
    "chain_creator_premium_content", "chain_creator_payouts",
    "chain_creator_gift_conversions", "chain_creator_revenue_reports",
    "chain_creator_sponsorships", "chain_creator_badges",
    "chain_supporter_badges", "chain_top_fans",
    "chain_creator_rankings", "chain_verification_requests",
    "chain_creator_analytics",
]
for tbl in creator_tables:
    if tbl in all_sql:
        check(f"DB table {tbl} defined in SQL", True)
    else:
        check(f"DB table {tbl} defined in SQL", False, "NOT FOUND")

# 5. Dashboard UI tabs
try:
    dash_html = open(os.path.join(BASE, "templates", "creator", "dashboard.html")).read()
    ui_tabs = [
        "Overview", "Earnings", "Gifts", "Live Earnings",
        "Subscriptions", "Paid Posts", "Premium Content",
        "Payouts", "Sponsorships", "Top Fans", "Badges", "Verification",
    ]
    for tab in ui_tabs:
        check(f"Dashboard tab: {tab}", tab.lower() in dash_html.lower(), f"tab '{tab}' not found")
except Exception as e:
    check("creator/dashboard.html readable", False, str(e))

print(f"\nResults: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")
if failed > 0:
    sys.exit(1)
