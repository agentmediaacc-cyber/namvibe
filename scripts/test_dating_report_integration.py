#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CHAIN_FAST_LOCAL", "0")

from psycopg2.extras import Json
from services.neon_service import fast_query, write_query
from services.dating_service import report_user


def create_profile(prefix):
    pid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    username = f"__dating_browser_test__{prefix}_{uuid.uuid4().hex[:8]}"
    write_query(
        """
        INSERT INTO chain_profiles (id, auth_user_id, username, display_name, full_name, email, bio, gender, age, date_of_birth, town, region, current_location, country_origin, profile_visibility, is_public, is_verified, dating_mode_enabled, relationship_goal, looking_for, interests, languages, avatar_url, cover_url, created_at, updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'public',true,true,true,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (pid, str(uuid.uuid4()), username, username, username, f"{username}@example.com", "report test", "female", 29, "1997-01-01", "Windhoek", "Khomas", "Windhoek", "Namibia", "serious", Json(["travel"]), Json(["travel"]), "english", "https://picsum.photos/seed/%s/600/600" % username, "https://picsum.photos/seed/%s/1200/600" % username, now, now),
    )
    write_query(
        "INSERT INTO chain_dating_profiles (id, profile_id, dating_mode_on, relationship_goal, age_range_min, age_range_max, location_preference, bio, interests, photos, verification_status, trust_score, safety_badge, hide_from_contacts, visible_to_verified_only, is_enabled, dating_intent, dating_interest, created_at, updated_at) VALUES (%s,%s,true,'relationship',18,40,'Windhoek','report test',%s,%s,'verified',90,true,false,false,true,'serious',%s,%s,%s)",
        (str(uuid.uuid4()), pid, ["travel"], [f"https://picsum.photos/seed/{username}/600/600"], ["travel"], now, now),
    )
    return pid


def cleanup(pids):
    for pid in pids:
        try:
            write_query("DELETE FROM chain_dating_reports WHERE reporter_profile_id = %s OR reported_profile_id = %s", (pid, pid))
            write_query("DELETE FROM chain_dating_blocks WHERE blocker_profile_id = %s OR blocked_profile_id = %s", (pid, pid))
            write_query("DELETE FROM chain_dating_likes WHERE actor_profile_id = %s OR target_profile_id = %s", (pid, pid))
            write_query("DELETE FROM chain_dating_matches WHERE profile_id_a = %s OR profile_id_b = %s", (pid, pid))
            write_query("DELETE FROM chain_dating_profiles WHERE profile_id = %s", (pid,))
            write_query("DELETE FROM chain_profiles WHERE id = %s", (pid,))
        except Exception:
            pass


def main():
    a = create_profile("reporter")
    b = create_profile("target")
    try:
        result = report_user(a, b, "spam", "testing")
        if not result.get("ok"):
            print("FAIL_APPLICATION")
            return 1
        rows = fast_query("SELECT id, reason, reporter_profile_id, reported_profile_id FROM chain_dating_reports WHERE reporter_profile_id = %s AND reported_profile_id = %s ORDER BY created_at DESC LIMIT 1", (a, b), timeout_ms=5000, default=[])
        if len(rows) != 1:
            print("FAIL_PROFILE")
            return 1
        if rows[0].get("reason") != "spam":
            print("FAIL_APPLICATION")
            return 1
        if report_user(a, a, "spam", "testing").get("error") != "cannot_report_self":
            print("FAIL_AUTHORIZATION")
            return 1
        if report_user(a, b, "invalid_reason", "testing").get("error") != "invalid_reason":
            print("FAIL_SCHEMA")
            return 1
        print("PASS")
        return 0
    finally:
        cleanup([a, b])


if __name__ == '__main__':
    raise SystemExit(main())
