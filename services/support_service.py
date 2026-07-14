import os
import uuid
from datetime import datetime, timezone

from flask import session
from services.neon_service import fetch_all, fetch_one, execute
from services.profile_service import get_current_profile
from services.logging_service import log_error, log_info

CATEGORIES = {
    "account_issue": "Account Issue",
    "login_problem": "Login Problem",
    "verification_problem": "Verification Problem",
    "payment_wallet_issue": "Payment/Wallet Issue",
    "marketplace_dispute": "Marketplace Dispute",
    "dating_safety": "Dating Safety Report",
    "fake_profile": "Fake Profile",
    "harassment_abuse": "Harassment or Abuse",
    "scam_fraud": "Scam/Fraud",
    "bug_report": "Bug in the App",
    "content_issue": "Post/Reel/Story Problem",
    "live_stream_issue": "Live Stream Problem",
    "message_call_issue": "Message/Call Problem",
    "business_advertising_issue": "Business/Advertising Issue",
}

STATUSES = ["open", "pending_support", "pending_user", "under_review", "escalated", "resolved", "closed", "rejected", "appealed"]
PRIORITIES = {"low": 0, "medium": 1, "high": 2, "urgent": 3}

def _profile_id():
    p = get_current_profile()
    return (p or {}).get("id")

def _utcnow():
    return datetime.now(timezone.utc)

def _generate_ticket_id(seq_id):
    year = _utcnow().strftime("%Y")
    return f"NV-TKT-{year}-{seq_id:06d}"

def _log_event(ticket_id, profile_id, agent_id, event_type, field_name=None, old_value=None, new_value=None, reason=None, ip_address=None):
    try:
        execute(
            """INSERT INTO chain_support_ticket_events
               (ticket_id, profile_id, agent_id, event_type, field_name, old_value, new_value, reason, ip_address)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (ticket_id, profile_id, agent_id, event_type, field_name, old_value, new_value, reason, ip_address),
            timeout_ms=5000,
        )
    except Exception as e:
        log_error("support_event_log_failed", ticket_id=ticket_id, error=str(e))

def _next_seq():
    row = fetch_one("SELECT nextval('chain_support_tickets_id_seq') AS seq", timeout_ms=3000)
    return row["seq"] if row else 1

def create_ticket(profile_id, subject, category, description, priority="medium", related_profile_id=None, related_post_id=None, related_reel_id=None, related_story_id=None, related_live_room_id=None, related_message_id=None, related_call_id=None, related_order_id=None, related_transaction_id=None, evidence_json=None):
    if category not in CATEGORIES:
        return None, "Invalid category"
    if priority not in PRIORITIES:
        priority = "medium"
    seq = _next_seq()
    ticket_id = _generate_ticket_id(seq)
    try:
        execute(
            """INSERT INTO chain_support_tickets
               (ticket_id, profile_id, subject, category, description, priority, status,
                related_profile_id, related_post_id, related_reel_id, related_story_id,
                related_live_room_id, related_message_id, related_call_id,
                related_order_id, related_transaction_id, evidence_json)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (ticket_id, profile_id, subject, category, description, priority, "open",
             related_profile_id, related_post_id, related_reel_id, related_story_id,
             related_live_room_id, related_message_id, related_call_id,
             related_order_id, related_transaction_id, evidence_json),
            timeout_ms=10000,
        )
        _log_event(None, profile_id, None, "created", new_value=ticket_id)
        return ticket_id, None
    except Exception as e:
        log_error("support_create_ticket_failed", error=str(e))
        return None, str(e)

def get_ticket(ticket_id, profile_id=None):
    if ticket_id.isdigit():
        row = fetch_one("SELECT * FROM chain_support_tickets WHERE id=%s", (int(ticket_id),), timeout_ms=5000)
    else:
        row = fetch_one("SELECT * FROM chain_support_tickets WHERE ticket_id=%s", (ticket_id,), timeout_ms=5000)
    if not row:
        return None
    if profile_id and row.get("profile_id") != profile_id:
        agent = is_agent(profile_id)
        if not agent:
            return None
    return dict(row)

def list_user_tickets(profile_id, status=None, limit=20, offset=0):
    if status:
        rows = fetch_all(
            "SELECT * FROM chain_support_tickets WHERE profile_id=%s AND status=%s ORDER BY last_activity_at DESC LIMIT %s OFFSET %s",
            (profile_id, status, limit, offset), timeout_ms=5000,
        )
    else:
        rows = fetch_all(
            "SELECT * FROM chain_support_tickets WHERE profile_id=%s ORDER BY last_activity_at DESC LIMIT %s OFFSET %s",
            (profile_id, limit, offset), timeout_ms=5000,
        )
    return [dict(r) for r in (rows or [])]

def _compute_priority(category, description=""):
    urgent_cats = {"payment_wallet_issue", "scam_fraud", "dating_safety", "harassment_abuse"}
    high_cats = {"verification_problem", "fake_profile", "live_stream_issue"}
    if category in urgent_cats:
        return "urgent"
    if category in high_cats:
        return "high"
    return "medium"

def _auto_assign(admin_profile_id):
    try:
        agents = fetch_all(
            "SELECT * FROM chain_support_agents WHERE is_active=TRUE ORDER BY assigned_count ASC LIMIT 1",
            timeout_ms=3000,
        )
        if agents:
            return agents[0]["id"]
    except Exception:
        pass
    return None

def add_user_message(ticket_id, profile_id, message):
    """Add a message from a user. Verifies ticket ownership and validates state.

    User may only reply when ticket status is: open, pending_support, pending_user,
    under_review, escalated, or appealed.

    User may NOT reply when ticket status is: resolved, closed, rejected.
    """
    ticket = get_ticket(ticket_id, profile_id=profile_id)
    if not ticket:
        return None, "ticket_not_found"
    tid = ticket["id"]
    # Validate ticket state - user can only reply in active states
    if ticket.get("status") in ("resolved", "closed", "rejected"):
        return None, "ticket_not_active"
    # User cannot set is_internal_note - it's always False
    try:
        execute(
            "INSERT INTO chain_support_ticket_messages (ticket_id, profile_id, is_agent, message, is_internal_note) VALUES (%s,%s,%s,%s,%s)",
            (tid, profile_id, False, message, False), timeout_ms=5000,
        )
        execute("UPDATE chain_support_tickets SET last_activity_at=%s WHERE id=%s", (_utcnow(), tid), timeout_ms=3000)
        _log_event(tid, profile_id, None, "message_added")
        return True, None
    except Exception as e:
        log_error("support_add_user_message_failed", error=str(e))
        return None, str(e)


def add_agent_message(ticket_id, agent_profile_id, message, is_internal_note=False):
    """Add a message from an agent. Verifies agent status and can create internal notes."""
    agent = is_agent(agent_profile_id)
    if not agent:
        return None, "not_authorized"
    ticket = get_ticket(ticket_id)
    if not ticket:
        return None, "ticket_not_found"
    tid = ticket["id"]
    try:
        execute(
            "INSERT INTO chain_support_ticket_messages (ticket_id, profile_id, is_agent, message, is_internal_note) VALUES (%s,%s,%s,%s,%s)",
            (tid, agent_profile_id, True, message, is_internal_note), timeout_ms=5000,
        )
        execute("UPDATE chain_support_tickets SET last_activity_at=%s WHERE id=%s", (_utcnow(), tid), timeout_ms=3000)
        _log_event(tid, agent_profile_id, agent["id"], "message_added")
        return True, None
    except Exception as e:
        log_error("support_add_agent_message_failed", error=str(e))
        return None, str(e)


def add_message(ticket_id, profile_id, message, is_agent=False, is_internal_note=False):
    """Legacy function - determines role from profile_id, ignores is_agent flag.

    DEPRECATED: Use add_user_message() or add_agent_message() directly.
    The is_agent parameter is ignored and authorization is determined by
    checking if the profile_id is an active support agent.
    """
    # Determine role from profile_id, not from the is_agent parameter
    # This prevents role spoofing via the API
    if is_agent(profile_id):
        return add_agent_message(ticket_id, profile_id, message, is_internal_note=is_internal_note)
    return add_user_message(ticket_id, profile_id, message)

def get_user_messages(ticket_id, profile_id):
    """Get messages for a user - filters out internal notes."""
    ticket = get_ticket(ticket_id, profile_id=profile_id)
    if not ticket:
        return []
    rows = fetch_all(
        "SELECT m.*, p.username, p.avatar_url FROM chain_support_ticket_messages m LEFT JOIN chain_profiles p ON m.profile_id=p.id WHERE m.ticket_id=%s AND m.is_internal_note=FALSE ORDER BY m.created_at ASC",
        (ticket["id"],), timeout_ms=5000,
    )
    return [dict(r) for r in (rows or [])]


def get_messages(ticket_id):
    """Get all messages including internal notes (for agents/admins)."""
    ticket = get_ticket(ticket_id)
    if not ticket:
        return []
    rows = fetch_all(
        "SELECT m.*, p.username, p.avatar_url FROM chain_support_ticket_messages m LEFT JOIN chain_profiles p ON m.profile_id=p.id WHERE m.ticket_id=%s ORDER BY m.created_at ASC",
        (ticket["id"],), timeout_ms=5000,
    )
    return [dict(r) for r in (rows or [])]

def update_ticket_status(ticket_id, new_status, agent_profile_id, reason=None):
    ticket = get_ticket(ticket_id)
    if not ticket:
        return False, "Ticket not found"
    if new_status not in STATUSES:
        return False, "Invalid status"
    old_status = ticket["status"]
    if old_status == new_status:
        return True, None
    try:
        execute("UPDATE chain_support_tickets SET status=%s, updated_at=%s WHERE id=%s", (new_status, _utcnow(), ticket["id"]), timeout_ms=5000)
        agent = is_agent(agent_profile_id)
        agent_id = agent["id"] if agent else None
        _log_event(ticket["id"], agent_profile_id, agent_id, "status_changed", "status", old_status, new_status, reason)
        if new_status == "resolved":
            execute("UPDATE chain_support_tickets SET resolved_at=%s WHERE id=%s", (_utcnow(), ticket["id"]), timeout_ms=3000)
        elif new_status == "escalated":
            execute("UPDATE chain_support_tickets SET escalated_at=%s WHERE id=%s", (_utcnow(), ticket["id"]), timeout_ms=3000)
            if reason:
                execute("UPDATE chain_support_tickets SET escalated_reason=%s WHERE id=%s", (reason, ticket["id"]), timeout_ms=3000)
        if new_status == "closed" and old_status == "resolved":
            pass
        if new_status == "open" and old_status in ("closed", "rejected", "resolved"):
            execute("UPDATE chain_support_tickets SET reopened_count=reopened_count+1 WHERE id=%s", (ticket["id"],), timeout_ms=3000)
        return True, None
    except Exception as e:
        log_error("support_update_status_failed", error=str(e))
        return False, str(e)

def assign_ticket(ticket_id, agent_profile_id, assigned_by_profile_id, reason=None):
    ticket = get_ticket(ticket_id)
    if not ticket:
        return False, "Ticket not found"
    agent = is_agent(agent_profile_id)
    if not agent:
        return False, "Profile is not a support agent"
    old_agent_id = ticket.get("assigned_to")
    try:
        execute("UPDATE chain_support_tickets SET assigned_to=%s, updated_at=%s WHERE id=%s", (agent["id"], _utcnow(), ticket["id"]), timeout_ms=5000)
        execute(
            "INSERT INTO chain_support_agent_assignments (ticket_id, agent_id, assigned_by, reason) VALUES (%s,%s,%s,%s)",
            (ticket["id"], agent["id"], assigned_by_profile_id, reason), timeout_ms=5000,
        )
        if old_agent_id:
            execute("UPDATE chain_support_agents SET assigned_count=GREATEST(assigned_count-1,0) WHERE id=%s", (old_agent_id,), timeout_ms=3000)
        execute("UPDATE chain_support_agents SET assigned_count=assigned_count+1 WHERE id=%s", (agent["id"],), timeout_ms=3000)
        _log_event(ticket["id"], assigned_by_profile_id, agent["id"], "assigned", "assigned_to", str(old_agent_id), str(agent["id"]), reason)
        return True, None
    except Exception as e:
        log_error("support_assign_failed", error=str(e))
        return False, str(e)

def is_agent(profile_id):
    if not profile_id:
        return None
    row = fetch_one("SELECT * FROM chain_support_agents WHERE profile_id=%s AND is_active=TRUE", (profile_id,), timeout_ms=3000)
    return row

def list_all_tickets(status=None, category=None, priority=None, assigned_to=None, limit=50, offset=0):
    conditions = []
    params = []
    if status:
        conditions.append("t.status=%s")
        params.append(status)
    if category:
        conditions.append("t.category=%s")
        params.append(category)
    if priority:
        conditions.append("t.priority=%s")
        params.append(priority)
    if assigned_to:
        conditions.append("t.assigned_to=%s")
        params.append(assigned_to)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    query = f"""SELECT t.*, p.username, p.avatar_url,
                a.display_name AS agent_name
                FROM chain_support_tickets t
                LEFT JOIN chain_profiles p ON t.profile_id=p.id
                LEFT JOIN chain_support_agents a ON t.assigned_to=a.id
                {where}
                ORDER BY t.priority DESC, t.last_activity_at DESC
                LIMIT %s OFFSET %s"""
    params.extend([limit, offset])
    rows = fetch_all(query, tuple(params), timeout_ms=8000)
    return [dict(r) for r in (rows or [])]

def count_tickets(status=None, category=None, priority=None):
    conditions = []
    params = []
    if status:
        conditions.append("status=%s")
        params.append(status)
    if category:
        conditions.append("category=%s")
        params.append(category)
    if priority:
        conditions.append("priority=%s")
        params.append(priority)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    row = fetch_one(f"SELECT COUNT(*) AS cnt FROM chain_support_tickets {where}", tuple(params) if params else None, timeout_ms=3000)
    return row["cnt"] if row else 0

def get_ticket_events(ticket_id):
    ticket = get_ticket(ticket_id)
    if not ticket:
        return []
    rows = fetch_all(
        """SELECT e.*, p.username, a.display_name AS agent_name
           FROM chain_support_ticket_events e
           LEFT JOIN chain_profiles p ON e.profile_id=p.id
           LEFT JOIN chain_support_agents a ON e.agent_id=a.id
           WHERE e.ticket_id=%s
           ORDER BY e.created_at ASC""",
        (ticket["id"],), timeout_ms=5000,
    )
    return [dict(r) for r in (rows or [])]

def get_help_articles(category_slug=None, limit=50):
    if category_slug:
        rows = fetch_all(
            """SELECT a.*, c.name AS category_name, c.slug AS category_slug
               FROM chain_support_help_articles a
               JOIN chain_support_faq_categories c ON a.category_id=c.id
               WHERE a.is_published=TRUE AND c.slug=%s
               ORDER BY a.views DESC LIMIT %s""",
            (category_slug, limit), timeout_ms=5000,
        )
    else:
        rows = fetch_all(
            """SELECT a.*, c.name AS category_name, c.slug AS category_slug
               FROM chain_support_help_articles a
               JOIN chain_support_faq_categories c ON a.category_id=c.id
               WHERE a.is_published=TRUE
               ORDER BY c.sort_order, a.views DESC LIMIT %s""",
            (limit,), timeout_ms=5000,
        )
    return [dict(r) for r in (rows or [])]

def get_help_article(slug):
    row = fetch_one(
        "SELECT a.*, c.name AS category_name, c.slug AS category_slug FROM chain_support_help_articles a JOIN chain_support_faq_categories c ON a.category_id=c.id WHERE a.slug=%s",
        (slug,), timeout_ms=5000,
    )
    if row:
        execute("UPDATE chain_support_help_articles SET views=views+1 WHERE id=%s", (row["id"],), timeout_ms=3000)
    return dict(row) if row else None

def get_faq_categories():
    rows = fetch_all(
        "SELECT c.*, (SELECT COUNT(*) FROM chain_support_help_articles WHERE category_id=c.id AND is_published=TRUE) AS article_count FROM chain_support_faq_categories c ORDER BY c.sort_order",
        timeout_ms=5000,
    )
    return [dict(r) for r in (rows or [])]

def add_feedback(ticket_id, profile_id, rating, comment=None):
    if rating < 1 or rating > 5:
        return False, "Rating must be between 1 and 5"
    ticket = get_ticket(ticket_id)
    if not ticket:
        return False, "Ticket not found"
    if ticket["profile_id"] != profile_id:
        return False, "Not your ticket"
    existing = fetch_one("SELECT id FROM chain_support_feedback WHERE ticket_id=%s", (ticket["id"],), timeout_ms=3000)
    if existing:
        return False, "Feedback already submitted"
    try:
        execute(
            "INSERT INTO chain_support_feedback (ticket_id, profile_id, rating, comment) VALUES (%s,%s,%s,%s)",
            (ticket["id"], profile_id, rating, comment), timeout_ms=5000,
        )
        return True, None
    except Exception as e:
        log_error("support_feedback_failed", error=str(e))
        return False, str(e)

def get_agent_stats(agent_id):
    open_count = count_tickets(status="open")
    pending_support = count_tickets(status="pending_support")
    pending_user = count_tickets(status="pending_user")
    escalated = count_tickets(status="escalated")
    resolved_today = fetch_one(
        "SELECT COUNT(*) AS cnt FROM chain_support_tickets WHERE status='resolved' AND resolved_at::date=CURRENT_DATE",
        timeout_ms=3000,
    )
    total_tickets = count_tickets()
    return {
        "open": open_count,
        "pending_support": pending_support,
        "pending_user": pending_user,
        "escalated": escalated,
        "resolved_today": resolved_today["cnt"] if resolved_today else 0,
        "total": total_tickets,
    }

def get_dashboard_stats():
    by_status = {}
    for s in STATUSES:
        by_status[s] = count_tickets(status=s)
    by_category = {}
    for c in CATEGORIES:
        cnt = count_tickets(category=c)
        if cnt:
            by_category[c] = cnt
    by_priority = {}
    for p in PRIORITIES:
        cnt = count_tickets(priority=p)
        if cnt:
            by_priority[p] = cnt
    total = sum(by_status.values())
    return {
        "by_status": by_status,
        "by_category": by_category,
        "by_priority": by_priority,
        "total": total,
    }

def get_agent_assignments(agent_id, limit=20):
    rows = fetch_all(
        """SELECT a.*, t.ticket_id, t.subject, t.status, t.priority, t.category, t.last_activity_at
           FROM chain_support_agent_assignments a
           JOIN chain_support_tickets t ON a.ticket_id=t.id
           WHERE a.agent_id=%s AND a.unassigned_at IS NULL
           ORDER BY a.assigned_at DESC LIMIT %s""",
        (agent_id, limit), timeout_ms=5000,
    )
    return [dict(r) for r in (rows or [])]
