#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CHAIN_FAST_LOCAL", "0")
os.environ.setdefault("FLASK_TESTING", "0")

from psycopg2.extras import Json
from services.neon_service import fast_query, write_query
from services.dating_service import get_discover_profiles, like_profile, get_matches, block_user, unmatch_users, report_user

RESULTS = []


def out(msg):
    print(msg)


def fail(code, msg):
    out(f"{code}: {msg}")
    raise SystemExit(1)


def pick_env_host():
    url = (os.getenv("DATABASE_URL") or os.getenv("DIRECT_DATABASE_URL") or "").strip()
    if "@" in url and "://" in url:
        host_part = url.split("@", 1)[1].split("/", 1)[0]
        host = host_part.split(":", 1)[0]
        return host
    return ""


def dns_probe(host):
    import socket
    try:
        socket.getaddrinfo(host, 5432)
        return True
    except Exception:
        return False


def create_profile(marker, suffix):
    pid = str(uuid.uuid4())
    auth_id = str(uuid.uuid4())
    username = f"{marker}_{suffix}_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    write_query(
        """
        INSERT INTO chain_profiles (
            id, auth_user_id, username, display_name, full_name, email,
            bio, gender, age, date_of_birth, town, region, current_location,
            country_origin, profile_visibility, is_public, is_verified,
            dating_mode_enabled, relationship_goal, looking_for, interests,
            languages, avatar_url, cover_url, created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, 'public', true, true,
            true, %s, %s, %s,
            %s, %s, %s, %s, %s
        )
        """,
        (
            pid, auth_id, username, username.replace("_", " ").title(), username.replace("_", " ").title(),
            f"{username}@example.com",
            f"Dating integration profile {suffix}",
            "female" if suffix == "b" else "male",
            29 if suffix == "a" else 27,
            "1997-01-01" if suffix == "a" else "1999-01-01",
            "Windhoek",
            "Khomas",
            "Windhoek",
            "Namibia",
            "serious",
            Json(["travel", "music", "food"]) if suffix == "a" else Json(["travel", "music", "coffee"]),
            Json(["travel", "music", "english"]),
            "english, oshiwambo",
            f"https://picsum.photos/seed/{username}/600/600",
            f"https://picsum.photos/seed/{username}/1200/600",
            now, now,
        ),
    )
    write_query(
        """
        INSERT INTO chain_dating_profiles (
            id, profile_id, dating_mode_on, relationship_goal, age_range_min, age_range_max,
            location_preference, bio, interests, photos, verification_status, trust_score,
            safety_badge, hide_from_contacts, visible_to_verified_only, is_enabled,
            dating_intent, dating_interest, created_at, updated_at
        ) VALUES (
            %s, %s, true, %s, 18, 40,
            %s, %s, %s, %s, 'verified', 90,
            true, false, false, true,
            %s, %s, %s, %s
        )
        """,
        (
            str(uuid.uuid4()), pid, "relationship",
            "Windhoek", f"Hello from {username}", ["travel", "music", "food"],
            [f"https://picsum.photos/seed/{username}/600/600"],
            "serious", ["travel", "music"], now, now,
        ),
    )
    write_query(
        """
        INSERT INTO chain_dating_preferences (
            id, profile_id, interested_in, min_age, max_age, max_distance_km,
            show_me, only_verified, hide_from_contacts, created_at, updated_at
        ) VALUES (%s, %s, %s, 18, 40, 200, true, true, false, %s, %s)
        """,
        (str(uuid.uuid4()), pid, "everyone", now, now),
    )
    return pid


def cleanup(profile_ids):
    for pid in profile_ids:
        try:
            write_query("DELETE FROM chain_notifications WHERE recipient_profile_id = %s OR actor_profile_id = %s", (pid, pid))
            write_query("DELETE FROM chain_dating_likes WHERE actor_profile_id = %s OR target_profile_id = %s", (pid, pid))
            write_query("DELETE FROM chain_dating_matches WHERE profile_id_a = %s OR profile_id_b = %s", (pid, pid))
            write_query("DELETE FROM chain_dating_blocks WHERE blocker_profile_id = %s OR blocked_profile_id = %s", (pid, pid))
            write_query("DELETE FROM chain_dating_preferences WHERE profile_id = %s", (pid,))
            write_query("DELETE FROM chain_dating_profiles WHERE profile_id = %s", (pid,))
            write_query("DELETE FROM chain_profiles WHERE id = %s", (pid,))
        except Exception:
            pass


def main():
    marker = f"dating_{uuid.uuid4().hex[:8]}"
    host = pick_env_host()
    if host and not dns_probe(host):
        print("BLOCKED_DNS")
        return 2

    profile_ids = []
    try:
        a = create_profile(marker, "a")
        b = create_profile(marker, "b")
        outsider = create_profile(marker, "c")
        profile_ids.extend([a, b, outsider])

        discover_a = get_discover_profiles(a, limit=10, offset=0)
        if not any(str(row.get("profile_id")) == str(b) for row in discover_a):
            fail("FAIL_DISCOVERY", "A cannot discover B")
        if any(str(row.get("profile_id")) == str(a) for row in discover_a):
            fail("FAIL_DISCOVERY", "A should not discover self")
        like_ab = like_profile(a, b)
        if not like_ab.get("ok") or like_ab.get("is_match"):
            fail("FAIL_MATCH", "A like should store without match")
        if get_matches(a, limit=10, offset=0):
            fail("FAIL_MATCH", "no active match should exist after one-sided like")

        like_ba = like_profile(b, a)
        if not like_ba.get("ok") or not like_ba.get("is_match"):
            fail("FAIL_MATCH", "reciprocal like should create match")
        match_rows = get_matches(a, limit=10, offset=0)
        if len(match_rows) != 1:
            fail("FAIL_MATCH", f"expected one active match, got {len(match_rows)}")

        notif_total = 0
        for table in ("chain_notification_events", "chain_notifications"):
            try:
                rows = fast_query(
                    f"SELECT id FROM {table} WHERE profile_id IN (%s, %s) ORDER BY created_at DESC LIMIT 20" if table == 'chain_notification_events' else f"SELECT id FROM {table} WHERE recipient_profile_id IN (%s, %s) ORDER BY created_at DESC LIMIT 20",
                    (a, b), timeout_ms=5000, default=[],
                )
                notif_total += len(rows or [])
            except Exception:
                pass
        if notif_total < 2:
            fail("FAIL_NOTIFICATION", "match notifications missing")

        unmatch_result = unmatch_users(a, b)
        if not unmatch_result.get("ok"):
            fail("FAIL_MATCH", "unmatch should succeed")
        if get_matches(a, limit=10, offset=0):
            fail("FAIL_MATCH", "match should be inactive after unmatch")
        if unmatch_users(a, b).get("status") not in {"already_inactive", "unmatched"}:
            fail("FAIL_MATCH", "duplicate unmatch should be idempotent")
        report_result = report_user(a, b, "spam", "testing")
        if not report_result.get("ok"):
            fail("FAIL_REPORT", "report should succeed")
        if not report_user(a, a, "spam", "testing").get("error") == "cannot_report_self":
            fail("FAIL_REPORT", "self report should reject")
        if report_user(a, b, "invalid_reason", "testing").get("error") != "invalid_reason":
            fail("FAIL_REPORT", "invalid reason should reject")
        if not block_user(a, b).get("ok"):
            fail("FAIL_BLOCK", "block should succeed")
        discover_after_block = get_discover_profiles(a, limit=10, offset=0)
        if any(str(row.get("profile_id")) == str(b) for row in discover_after_block):
            fail("FAIL_BLOCK", "blocked profile should disappear from discovery")

        print("PASS")
        return 0
    except SystemExit as exc:
        return int(exc.code or 1)
    except Exception as exc:
        fail("FAIL_APPLICATION", type(exc).__name__ + ": " + str(exc))
    finally:
        cleanup(profile_ids)
        verify = fast_query(
            "SELECT COUNT(*) AS cnt FROM chain_profiles WHERE username LIKE %s",
            (f"{marker}%",), timeout_ms=5000, default=[],
        )
        if verify and int(verify[0]["cnt"] or 0) == 0:
            out("cleanup=ok")
        else:
            out("cleanup=partial")


if __name__ == "__main__":
    raise SystemExit(main())
