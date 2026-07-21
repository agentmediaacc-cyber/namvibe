#!/usr/bin/env python3
"""Verify seeded/test users are excluded from production public surfaces."""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

SEED_USERS = {"chain_star", "chain_moon", "chain_gold", "chain_million"}
PUBLIC_QUERY_FILES = {
    "homepage": ROOT / "services" / "homepage_service.py",
    "trending_creators": ROOT / "services" / "homepage_service.py",
    "suggested_users": ROOT / "services" / "recommendation_service.py",
    "creator_discovery": ROOT / "services" / "discovery_service.py",
    "dating_discovery": ROOT / "services" / "dating_service.py",
    "matching_discovery": ROOT / "services" / "matching_service.py",
    "search_results": ROOT / "services" / "search_service.py",
    "follow_suggestions": ROOT / "services" / "recommendation_service.py",
}


def read(path):
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def check_filter_runtime():
    from services.homepage_real_data_guard import filter_feed_posts, filter_profiles, is_test_profile

    offenders = []
    for username in sorted(SEED_USERS):
        profile = {"id": username, "username": username, "email": f"{username}@chain.local"}
        if not is_test_profile(profile):
            offenders.append(f"filter:is_test_profile did not catch {username}")
        if filter_profiles([profile]):
            offenders.append(f"filter:filter_profiles leaked {username}")
        if filter_feed_posts([{"id": username, "username": username, "profile_id": username}]):
            offenders.append(f"filter:filter_feed_posts leaked {username}")

    return offenders


def check_public_query_sources():
    offenders = []
    required_tokens = {
        "services/homepage_service.py": ("public_profile_sql", "public_profile_subquery", "filter_profiles", "filter_feed_posts"),
        "services/recommendation_service.py": ("public_profile_sql", "filter_profiles"),
        "services/discovery_service.py": ("public_profile_sql", "public_profile_subquery", "filter_profiles", "filter_feed_posts"),
        "services/search_service.py": ("public_profile_sql", "public_profile_subquery", "filter_profiles", "filter_feed_posts"),
        "services/dating_service.py": ("public_profile_sql",),
        "services/matching_service.py": ("is_test_profile",),
    }
    for rel, tokens in required_tokens.items():
        text = read(ROOT / rel)
        for token in tokens:
            if token not in text:
                offenders.append(f"{rel}: missing {token}")

    homepage = read(ROOT / "services" / "homepage_service.py")
    if "WHERE is_creator = TRUE" in homepage and "public_profile_sql('chain_profiles')" not in homepage:
        offenders.append("homepage/trending creators query missing public_profile_sql")
    if "chain_posts WHERE deleted_at IS NULL" in homepage and "public_profile_subquery()" not in homepage:
        offenders.append("homepage feed queries missing public_profile_subquery")

    search = read(ROOT / "services" / "search_service.py")
    if "FROM chain_profiles" in search and "public_profile_sql(\"chain_profiles\")" not in search:
        offenders.append("search profile query missing public_profile_sql")
    if "FROM chain_posts" in search and "public_profile_subquery()" not in search:
        offenders.append("search content query missing public_profile_subquery")

    return offenders


def check_credentials_not_exposed():
    offenders = []
    public_files = [
        ROOT / "services" / "homepage_service.py",
        ROOT / "services" / "discovery_service.py",
        ROOT / "services" / "search_service.py",
        ROOT / "services" / "dating_service.py",
        ROOT / "services" / "recommendation_service.py",
        ROOT / "templates" / "chain_home.html",
        ROOT / "templates" / "discover" / "index.html",
        ROOT / "templates" / "search" / "index.html",
    ]
    forbidden = ("password_hash", "Adimintest", "test_credentials.json")
    for path in public_files:
        text = read(path)
        for token in forbidden:
            if token in text:
                offenders.append(f"{path.relative_to(ROOT)} exposes {token}")
    return offenders


def main():
    offenders = []
    offenders.extend(check_filter_runtime())
    offenders.extend(check_public_query_sources())
    offenders.extend(check_credentials_not_exposed())

    if offenders:
        print("FAIL")
        print("Offending queries/findings:")
        for item in offenders:
            print(f"- {item}")
        return 1

    print("PASS")
    print("Offending queries/findings: none")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
