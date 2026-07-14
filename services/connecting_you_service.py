"""Connecting You — NamVibe Dating Program Service"""

import json
import math
from datetime import datetime, timezone
from services.neon_service import execute, fetch_one, fetch_all, fast_query


# ─── ENROLLMENT ───────────────────────────────────────────

def enroll(profile_id, data):
    """Enroll a user in the Connecting You program."""
    existing = fetch_one(
        "SELECT id, status FROM chain_cy_enrollments WHERE profile_id = %s",
        (profile_id,)
    )
    if existing and existing.get("status") in ("approved", "active"):
        return {"ok": False, "error": "Already enrolled"}

    goal = (data.get("relationship_goal") or "serious")[:32]
    languages = data.get("languages", [])
    if isinstance(languages, str):
        languages = [l.strip() for l in languages.split(",") if l.strip()]

    execute(
        """INSERT INTO chain_cy_enrollments
           (profile_id, relationship_goal, religion, languages, tribe, region, town,
            occupation, education, personality_type, love_language, communication_style,
            faith_importance, wants_children, would_relocate, financial_habits,
            conflict_style, status)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending')
           ON CONFLICT (profile_id) DO UPDATE SET
            relationship_goal = EXCLUDED.relationship_goal,
            religion = EXCLUDED.religion,
            languages = EXCLUDED.languages,
            tribe = EXCLUDED.tribe,
            region = EXCLUDED.region,
            town = EXCLUDED.town,
            occupation = EXCLUDED.occupation,
            education = EXCLUDED.education,
            personality_type = EXCLUDED.personality_type,
            love_language = EXCLUDED.love_language,
            communication_style = EXCLUDED.communication_style,
            faith_importance = EXCLUDED.faith_importance,
            wants_children = EXCLUDED.wants_children,
            would_relocate = EXCLUDED.would_relocate,
            financial_habits = EXCLUDED.financial_habits,
            conflict_style = EXCLUDED.conflict_style,
            updated_at = NOW()""",
        (profile_id, goal, data.get("religion", ""), languages,
         data.get("tribe", ""), data.get("region", ""), data.get("town", ""),
         data.get("occupation", ""), data.get("education", ""),
         data.get("personality_type", ""), data.get("love_language", ""),
         data.get("communication_style", ""), data.get("faith_importance", ""),
         data.get("wants_children", ""), data.get("would_relocate", ""),
         data.get("financial_habits", ""), data.get("conflict_style", ""))
    )
    return {"ok": True, "status": "pending"}


def get_enrollment(profile_id):
    """Get a user's enrollment record."""
    return fetch_one(
        "SELECT * FROM chain_cy_enrollments WHERE profile_id = %s",
        (profile_id,)
    )


def update_enrollment_status(profile_id, status, verified=False):
    """Update enrollment status (admin action)."""
    if verified:
        execute(
            "UPDATE chain_cy_enrollments SET status = %s, verified = TRUE, verified_at = NOW(), updated_at = NOW() WHERE profile_id = %s",
            (status, profile_id)
        )
    else:
        execute(
            "UPDATE chain_cy_enrollments SET status = %s, updated_at = NOW() WHERE profile_id = %s",
            (status, profile_id)
        )
    return {"ok": True}


def list_enrollments(status=None, region=None, limit=50, offset=0):
    """List enrollments for admin dashboard."""
    where = []
    params = []
    if status:
        where.append("e.status = %s")
        params.append(status)
    if region:
        where.append("e.region = %s")
        params.append(region)

    where_clause = " WHERE " + " AND ".join(where) if where else ""
    params.extend([limit, offset])

    rows = fetch_all(
        f"""SELECT e.*, p.username, p.display_name, p.avatar_url, p.is_verified,
                   p.age, p.gender
            FROM chain_cy_enrollments e
            JOIN chain_profiles p ON p.id = e.profile_id
            {where_clause}
            ORDER BY e.enrolled_at DESC LIMIT %s OFFSET %s""",
        tuple(params)
    )
    return rows or []


# ─── ASSESSMENTS ──────────────────────────────────────────

def get_assessment_questions():
    """Get all active assessment questions."""
    return fetch_all(
        "SELECT * FROM chain_cy_assessment_questions WHERE is_active = TRUE ORDER BY sort_order ASC",
        ()
    ) or []


def submit_assessment(profile_id, answers):
    """Submit assessment answers. answers = [{question_id, answer}, ...]"""
    for item in answers:
        qid = item.get("question_id")
        answer = item.get("answer", "")
        if qid and answer:
            execute(
                """INSERT INTO chain_cy_assessment_responses (profile_id, question_id, answer)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (profile_id, question_id) DO UPDATE SET answer = EXCLUDED.answer, answered_at = NOW()""",
                (profile_id, qid, answer)
            )
    score = calculate_compatibility_score(profile_id)
    execute(
        "UPDATE chain_cy_enrollments SET compatibility_score = %s, updated_at = NOW() WHERE profile_id = %s",
        (score, profile_id)
    )
    return {"ok": True, "score": score}


def get_assessment_responses(profile_id):
    """Get a user's assessment responses."""
    return fetch_all(
        """SELECT r.*, q.category, q.question, q.options
           FROM chain_cy_assessment_responses r
           JOIN chain_cy_assessment_questions q ON q.id = r.question_id
           WHERE r.profile_id = %s
           ORDER BY q.sort_order""",
        (profile_id,)
    ) or []


def calculate_compatibility_score(profile_id):
    """Calculate a user's overall assessment score (0-100) based on completeness."""
    responses = get_assessment_responses(profile_id)
    questions = get_assessment_questions()
    if not questions:
        return 0
    total_weight = sum(float(q.get("weight", 1)) for q in questions)
    answered_weight = sum(float(r.get("weight", 1)) for r in responses)
    return round((answered_weight / total_weight) * 100, 1) if total_weight > 0 else 0


# ─── COMPATIBILITY ────────────────────────────────────────

CATEGORY_WEIGHTS = {
    "conflict": 1.5,
    "values": 1.3,
    "communication": 1.4,
    "finance": 1.2,
    "faith": 1.0,
    "lifestyle": 0.8,
    "future": 1.0,
}


def calculate_pair_compatibility(profile_a, profile_b):
    """Calculate compatibility between two profiles based on assessment answers."""
    responses_a = fetch_all(
        "SELECT question_id, answer FROM chain_cy_assessment_responses WHERE profile_id = %s",
        (profile_a,)
    ) or []
    responses_b = fetch_all(
        "SELECT question_id, answer FROM chain_cy_assessment_responses WHERE profile_id = %s",
        (profile_b,)
    ) or []

    if not responses_a or not responses_b:
        return 0, {}

    answers_a = {r["question_id"]: r["answer"] for r in responses_a}
    answers_b = {r["question_id"]: r["answer"] for r in responses_b}

    questions = fetch_all(
        "SELECT id, category, weight FROM chain_cy_assessment_questions WHERE is_active = TRUE",
        ()
    ) or []

    category_scores = {}
    total_score = 0
    total_weight = 0

    for q in questions:
        qid = q["id"]
        if qid in answers_a and qid in answers_b:
            a_val = answers_a[qid]
            b_val = answers_b[qid]
            match = 100 if a_val == b_val else 50
            cat = q["category"]
            w = float(q.get("weight", 1)) * CATEGORY_WEIGHTS.get(cat, 1.0)
            if cat not in category_scores:
                category_scores[cat] = {"score": 0, "weight": 0}
            category_scores[cat]["score"] += match * w
            category_scores[cat]["weight"] += w
            total_score += match * w
            total_weight += w

    for cat in category_scores:
        cs = category_scores[cat]
        cs["score"] = round(cs["score"] / cs["weight"], 1) if cs["weight"] > 0 else 0

    overall = round(total_score / total_weight, 1) if total_weight > 0 else 0
    return overall, category_scores


def find_top_matches(profile_id, limit=20):
    """Find top compatibility matches for a user."""
    enrollment = get_enrollment(profile_id)
    if not enrollment or enrollment.get("status") not in ("approved", "active"):
        return []

    goal = enrollment.get("relationship_goal", "")
    region = enrollment.get("region", "")
    gender_pref = "female" if enrollment.get("gender") == "male" else "male"

    candidates = fetch_all(
        """SELECT e.profile_id, p.username, p.display_name, p.avatar_url,
                  p.age, p.gender, p.is_verified, e.compatibility_score,
                  e.region, e.town, e.relationship_goal, e.occupation,
                  e.personality_type, e.love_language
           FROM chain_cy_enrollments e
           JOIN chain_profiles p ON p.id = e.profile_id
           WHERE e.status = 'active' AND e.profile_id != %s
           ORDER BY e.compatibility_score DESC LIMIT %s""",
        (profile_id, limit * 3)
    ) or []

    scored = []
    for c in candidates:
        overall, categories = calculate_pair_compatibility(profile_id, c["profile_id"])
        c["match_score"] = overall
        c["category_scores"] = categories
        scored.append(c)

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return scored[:limit]


# ─── INTRODUCTIONS ────────────────────────────────────────

def create_introduction(profile_a, profile_b, admin_id=None, notes=""):
    """Admin creates an introduction between two users."""
    compat, cats = calculate_pair_compatibility(profile_a, profile_b)
    intro_id = fetch_one(
        """INSERT INTO chain_cy_introductions
           (profile_a, profile_b, compatibility_score, admin_notes, introduced_by, status)
           VALUES (%s, %s, %s, %s, %s, 'pending')
           RETURNING id""",
        (profile_a, profile_b, compat, notes, admin_id)
    )
    if intro_id:
        _notify_introduction(profile_a, "You have a potential match!")
        _notify_introduction(profile_b, "You have a potential match!")
        return {"ok": True, "intro_id": str(intro_id["id"]), "compatibility": compat}
    return {"ok": False, "error": "Failed to create introduction"}


def respond_to_introduction(profile_id, intro_id, response):
    """User responds to an introduction. response = 'accept' | 'decline' | 'maybe'"""
    intro = fetch_one(
        "SELECT * FROM chain_cy_introductions WHERE id = %s",
        (intro_id,)
    )
    if not intro:
        return {"ok": False, "error": "Introduction not found"}

    is_a = str(intro.get("profile_a")) == str(profile_id)
    is_b = str(intro.get("profile_b")) == str(profile_id)
    if not is_a and not is_b:
        return {"ok": False, "error": "Not your introduction"}

    col = "a_response" if is_a else "b_response"
    execute(
        f"UPDATE chain_cy_introductions SET {col} = %s, responded_at = NOW() WHERE id = %s",
        (response, intro_id)
    )

    updated = fetch_one("SELECT * FROM chain_cy_introductions WHERE id = %s", (intro_id,))
    if updated and updated.get("a_response") == "accept" and updated.get("b_response") == "accept":
        execute(
            "UPDATE chain_cy_introductions SET status = 'matched', matched_at = NOW() WHERE id = %s",
            (intro_id,)
        )
        _create_match(updated["profile_a"], updated["profile_b"], intro_id)
        return {"ok": True, "matched": True}

    if updated and (updated.get("a_response") == "decline" or updated.get("b_response") == "decline"):
        execute(
            "UPDATE chain_cy_introductions SET status = 'declined' WHERE id = %s",
            (intro_id,)
        )
        return {"ok": True, "matched": False, "declined": True}

    return {"ok": True, "matched": False, "pending": True}


def get_introductions(profile_id, status=None):
    """Get introductions for a user."""
    where = "(profile_a = %s OR profile_b = %s)"
    params = [profile_id, profile_id]
    if status:
        where += " AND status = %s"
        params.append(status)
    return fetch_all(
        f"""SELECT i.*,
                   pa.username as a_username, pa.display_name as a_name, pa.avatar_url as a_avatar,
                   pb.username as b_username, pb.display_name as b_name, pb.avatar_url as b_avatar
            FROM chain_cy_introductions i
            JOIN chain_profiles pa ON pa.id = i.profile_a
            JOIN chain_profiles pb ON pb.id = i.profile_b
            WHERE {where}
            ORDER BY i.introduced_at DESC""",
        tuple(params)
    ) or []


# ─── MATCHES ──────────────────────────────────────────────

def _create_match(profile_a, profile_b, introduction_id=None):
    """Create a match record and open a chat."""
    execute(
        """INSERT INTO chain_cy_matches (profile_a, profile_b, introduction_id)
           VALUES (%s, %s, %s)
           ON CONFLICT (profile_a, profile_b) DO NOTHING""",
        (profile_a, profile_b, introduction_id)
    )
    _notify_introduction(profile_a, "It's a match! You can now chat.")
    _notify_introduction(profile_b, "It's a match! You can now chat.")


def get_matches(profile_id):
    """Get all matches for a user."""
    return fetch_all(
        """SELECT m.*,
                  pa.username as a_username, pa.display_name as a_name, pa.avatar_url as a_avatar,
                  pb.username as b_username, pb.display_name as b_name, pb.avatar_url as b_avatar
           FROM chain_cy_matches m
           JOIN chain_profiles pa ON pa.id = m.profile_a
           JOIN chain_profiles pb ON pb.id = m.profile_b
           WHERE (m.profile_a = %s OR m.profile_b = %s) AND m.status = 'active'
           ORDER BY m.match_date DESC""",
        (profile_id, profile_id)
    ) or []


def get_match_stats():
    """Get platform-wide match statistics."""
    total = fetch_one("SELECT COUNT(*) as cnt FROM chain_cy_matches WHERE status = 'active'")
    stories = fetch_one("SELECT COUNT(*) as cnt FROM chain_cy_success_stories WHERE is_public = TRUE")
    enrolled = fetch_one("SELECT COUNT(*) as cnt FROM chain_cy_enrollments")
    verified = fetch_one("SELECT COUNT(*) as cnt FROM chain_cy_enrollments WHERE verified = TRUE")
    return {
        "total_matches": total["cnt"] if total else 0,
        "success_stories": stories["cnt"] if stories else 0,
        "total_enrolled": enrolled["cnt"] if enrolled else 0,
        "verified_members": verified["cnt"] if verified else 0,
    }


# ─── EVENTS ───────────────────────────────────────────────

def list_events(event_type=None, region=None, status="scheduled", limit=20):
    """List Connecting You events."""
    where = ["status = %s"]
    params = [status]
    if event_type:
        where.append("event_type = %s")
        params.append(event_type)
    if region:
        where.append("(region = %s OR region = 'all')")
        params.append(region)

    params.append(limit)
    return fetch_all(
        f"""SELECT e.*, m.name as mentor_name, m.title as mentor_title
            FROM chain_cy_events e
            LEFT JOIN chain_cy_mentors m ON m.id = e.mentor_id
            WHERE {' AND '.join(where)}
            ORDER BY e.event_date ASC LIMIT %s""",
        tuple(params)
    ) or []


def get_event(event_id):
    """Get a single event."""
    return fetch_one(
        """SELECT e.*, m.name as mentor_name, m.title as mentor_title
           FROM chain_cy_events e
           LEFT JOIN chain_cy_mentors m ON m.id = e.mentor_id
           WHERE e.id = %s""",
        (event_id,)
    )


def register_for_event(event_id, profile_id):
    """Register a user for an event."""
    existing = fetch_one(
        "SELECT id FROM chain_cy_event_registrations WHERE event_id = %s AND profile_id = %s",
        (event_id, profile_id)
    )
    if existing:
        return {"ok": False, "error": "Already registered"}

    event = get_event(event_id)
    if not event:
        return {"ok": False, "error": "Event not found"}

    max_p = event.get("max_participants", 0)
    if max_p > 0 and event.get("current_participants", 0) >= max_p:
        execute(
            """INSERT INTO chain_cy_event_registrations (event_id, profile_id, status)
               VALUES (%s, %s, 'waitlisted')""",
            (event_id, profile_id)
        )
        return {"ok": True, "status": "waitlisted"}

    execute(
        """INSERT INTO chain_cy_event_registrations (event_id, profile_id)
           VALUES (%s, %s) ON CONFLICT DO NOTHING""",
        (event_id, profile_id)
    )
    execute(
        "UPDATE chain_cy_events SET current_participants = current_participants + 1 WHERE id = %s",
        (event_id,)
    )
    return {"ok": True, "status": "registered"}


def create_event(data):
    """Admin creates a new event."""
    row = fetch_one(
        """INSERT INTO chain_cy_events
           (event_type, title, description, region, max_participants, event_date,
            duration_minutes, venue, venue_address, is_virtual, tags)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           RETURNING id""",
        (data.get("event_type", "meet_up"),
         data.get("title", ""),
         data.get("description", ""),
         data.get("region", "all"),
         data.get("max_participants", 0),
         data.get("event_date"),
         data.get("duration_minutes", 60),
         data.get("venue", ""),
         data.get("venue_address", ""),
         data.get("is_virtual", True),
         data.get("tags", []))
    )
    return {"ok": True, "event_id": str(row["id"]) if row else None}


# ─── BALLOON POPS ─────────────────────────────────────────

def pop_balloon(event_id, admin_id):
    """Admin pops a random balloon — reveals a participant."""
    participant = fetch_one(
        """SELECT er.profile_id, p.display_name, p.age, p.avatar_url
           FROM chain_cy_event_registrations er
           JOIN chain_profiles p ON p.id = er.profile_id
           WHERE er.event_id = %s AND er.status = 'registered'
           ORDER BY RANDOM() LIMIT 1""",
        (event_id,)
    )
    if not participant:
        return {"ok": False, "error": "No participants to pop"}

    pid = participant["profile_id"]
    enrollment = get_enrollment(pid)
    interests = []
    if enrollment:
        interests = enrollment.get("languages", []) or []
        if enrollment.get("occupation"):
            interests.append(enrollment["occupation"])

    pop = fetch_one(
        """INSERT INTO chain_cy_balloon_pops
           (event_id, popped_profile_id, revealed_name, revealed_age, revealed_region, revealed_interests)
           VALUES (%s, %s, %s, %s, %s, %s)
           RETURNING id""",
        (event_id, pid,
         participant.get("display_name") or "Member",
         participant.get("age", 0),
         (enrollment or {}).get("region", ""),
         interests)
    )
    return {
        "ok": True,
        "pop_id": str(pop["id"]) if pop else None,
        "name": participant.get("display_name") or "Member",
        "age": participant.get("age", 0),
        "region": (enrollment or {}).get("region", ""),
        "interests": interests,
    }


def express_interest(balloon_pop_id, expressor_id):
    """User expresses interest after a balloon pop."""
    existing = fetch_one(
        "SELECT id FROM chain_cy_balloon_interests WHERE balloon_pop_id = %s AND expressor_id = %s",
        (balloon_pop_id, expressor_id)
    )
    if existing:
        return {"ok": False, "error": "Already expressed interest"}

    execute(
        """INSERT INTO chain_cy_balloon_interests (balloon_pop_id, expressor_id)
           VALUES (%s, %s)""",
        (balloon_pop_id, expressor_id)
    )
    pop = fetch_one("SELECT * FROM chain_cy_balloon_pops WHERE id = %s", (balloon_pop_id,))
    if pop:
        execute(
            "UPDATE chain_cy_balloon_pops SET interest_count = interest_count + 1 WHERE id = %s",
            (balloon_pop_id,)
        )
    return {"ok": True}


# ─── SUCCESS STORIES ──────────────────────────────────────

def submit_success_story(data):
    """Submit a success story."""
    row = fetch_one(
        """INSERT INTO chain_cy_success_stories
           (couple_names, region, story, photo_urls, wedding_photo_url, submitted_by)
           VALUES (%s,%s,%s,%s,%s,%s)
           RETURNING id""",
        (data.get("couple_names", ""),
         data.get("region", ""),
         data.get("story", ""),
         data.get("photo_urls", []),
         data.get("wedding_photo_url", ""),
         data.get("submitted_by"))
    )
    return {"ok": True, "story_id": str(row["id"]) if row else None}


def get_success_stories(featured_only=False, limit=12):
    """Get public success stories."""
    where = "is_public = TRUE"
    if featured_only:
        where += " AND is_featured = TRUE"
    return fetch_all(
        f"SELECT * FROM chain_cy_success_stories WHERE {where} ORDER BY submitted_at DESC LIMIT %s",
        (limit,)
    ) or []


# ─── MENTORS ──────────────────────────────────────────────

def list_mentors():
    """List active mentors."""
    return fetch_all(
        "SELECT * FROM chain_cy_mentors WHERE is_active = TRUE ORDER BY name ASC",
        ()
    ) or []


def list_all_mentors():
    """List all mentors (admin)."""
    return fetch_all(
        "SELECT * FROM chain_cy_mentors ORDER BY created_at DESC",
        ()
    ) or []


def create_mentor(data):
    """Admin creates a mentor profile."""
    row = fetch_one(
        """INSERT INTO chain_cy_mentors (name, title, specialty, bio, avatar_url, profile_id)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (data.get("name", ""), data.get("title", ""), data.get("specialty", ""),
         data.get("bio", ""), data.get("avatar_url", ""), data.get("profile_id"))
    )
    return {"ok": True, "mentor_id": row["id"] if row else None}


def toggle_mentor(mentor_id, is_active):
    """Admin activates/deactivates a mentor."""
    execute(
        "UPDATE chain_cy_mentors SET is_active = %s WHERE id = %s",
        (is_active, mentor_id)
    )
    return {"ok": True}


# ─── ANNOUNCEMENTS ────────────────────────────────────────

def create_announcement(data):
    """Admin creates a dating program announcement."""
    row = fetch_one(
        """INSERT INTO chain_cy_announcements (title, body, audience, region, priority)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (data.get("title", ""), data.get("body", ""),
         data.get("audience", "all"), data.get("region", ""),
         data.get("priority", "normal"))
    )
    return {"ok": True, "announcement_id": str(row["id"]) if row else None}


def list_announcements(audience=None, limit=20):
    """List active announcements."""
    where = "is_active = TRUE"
    params = []
    if audience:
        where += " AND (audience = %s OR audience = 'all')"
        params.append(audience)
    params.append(limit)
    return fetch_all(
        f"SELECT * FROM chain_cy_announcements WHERE {where} ORDER BY created_at DESC LIMIT %s",
        tuple(params)
    ) or []


# ─── ADMIN EVENTS ─────────────────────────────────────────

def list_events_admin(status=None, limit=50):
    """List all events for admin."""
    where = ""
    params = []
    if status:
        where = "WHERE e.status = %s"
        params.append(status)
    params.append(limit)
    return fetch_all(
        f"""SELECT e.*, m.name as mentor_name, m.title as mentor_title
            FROM chain_cy_events e
            LEFT JOIN chain_cy_mentors m ON m.id = e.mentor_id
            {where}
            ORDER BY e.event_date DESC LIMIT %s""",
        tuple(params)
    ) or []


def update_event_status(event_id, status):
    """Admin updates event status."""
    execute(
        "UPDATE chain_cy_events SET status = %s, updated_at = NOW() WHERE id = %s",
        (status, event_id)
    )
    return {"ok": True}


# ─── NOTIFICATIONS ────────────────────────────────────────

def _notify_introduction(profile_id, message):
    """Send a notification about an introduction."""
    try:
        from services.notification_engine import create_notification
        create_notification(
            profile_id=profile_id,
            notification_type="dating",
            title="Connecting You",
            body=message,
        )
    except Exception:
        pass


# ─── ADMIN STATS ──────────────────────────────────────────

def get_admin_stats():
    """Get comprehensive admin stats for the dating program."""
    enrolled = fetch_one("SELECT COUNT(*) as c FROM chain_cy_enrollments")
    pending = fetch_one("SELECT COUNT(*) as c FROM chain_cy_enrollments WHERE status = 'pending'")
    active = fetch_one("SELECT COUNT(*) as c FROM chain_cy_enrollments WHERE status = 'active'")
    verified = fetch_one("SELECT COUNT(*) as c FROM chain_cy_enrollments WHERE verified = TRUE")
    matches = fetch_one("SELECT COUNT(*) as c FROM chain_cy_matches WHERE status = 'active'")
    stories = fetch_one("SELECT COUNT(*) as c FROM chain_cy_success_stories WHERE is_public = TRUE")
    intros = fetch_one("SELECT COUNT(*) as c FROM chain_cy_introductions")
    events = fetch_one("SELECT COUNT(*) as c FROM chain_cy_events WHERE status = 'scheduled'")

    region_dist = fetch_all(
        "SELECT region, COUNT(*) as c FROM chain_cy_enrollments WHERE region != '' GROUP BY region ORDER BY c DESC",
        ()
    ) or []

    goal_dist = fetch_all(
        "SELECT relationship_goal, COUNT(*) as c FROM chain_cy_enrollments GROUP BY relationship_goal ORDER BY c DESC",
        ()
    ) or []

    return {
        "total_enrolled": enrolled["c"] if enrolled else 0,
        "pending_approval": pending["c"] if pending else 0,
        "active_members": active["c"] if active else 0,
        "verified_members": verified["c"] if verified else 0,
        "active_matches": matches["c"] if matches else 0,
        "success_stories": stories["c"] if stories else 0,
        "total_introductions": intros["c"] if intros else 0,
        "upcoming_events": events["c"] if events else 0,
        "region_distribution": [{"region": r["region"], "count": r["c"]} for r in region_dist],
        "goal_distribution": [{"goal": r["relationship_goal"], "count": r["c"]} for r in goal_dist],
    }


NAMIBIA_REGIONS = [
    "Windhoek", "Swakopmund", "Walvis Bay", "Oshakati", "Ongwediva",
    "Rundu", "Keetmanshoop", "Otjiwarongo", "Gobabis", "Katima Mulilo",
    "Grootfontein", "Tsumeb", "Outjo", "Usakos", "Mariental",
]
