"""Inbox routes — simplified messaging inbox with tabs."""
from flask import Blueprint, render_template, request
from services.profile_service import get_current_profile
from services.neon_service import fast_query, get_cached_table_columns


def _thread_name_expr(table_alias="t"):
    cols = get_cached_table_columns("chain_message_threads") or set()
    for col in ("thread_name", "title", "name", "display_name"):
        if col in cols:
            return f"{table_alias}.{col}"
    return "'Conversation'"

inbox_bp = Blueprint("inbox", __name__, url_prefix="/inbox")


def _profile():
    return get_current_profile()


@inbox_bp.route("/")
def inbox_main():
    profile = _profile()
    if not profile:
        return render_template("auth/login.html", error="Please log in.")
    pid = profile["id"]
    tn = _thread_name_expr("t")
    conversations = fast_query(
        f"""
        SELECT
          t.id,
          t.thread_type,
          COALESCE({tn}, '') AS display_name,
          (SELECT p.avatar_url FROM chain_profiles p
           JOIN chain_thread_members tm2 ON tm2.profile_id = p.id
           WHERE tm2.thread_id = t.id AND tm2.profile_id != %s LIMIT 1) AS avatar_url,
          (SELECT m.body FROM chain_messages m
           WHERE m.thread_id = t.id ORDER BY m.created_at DESC LIMIT 1) AS last_message,
          (SELECT MAX(m.created_at) FROM chain_messages m
           WHERE m.thread_id = t.id) AS last_message_at
        FROM chain_message_threads t
        JOIN chain_thread_members tm ON tm.thread_id = t.id
        WHERE tm.profile_id = %s
          AND t.deleted_at IS NULL
          AND (tm.is_archived IS NULL OR tm.is_archived = FALSE)
        ORDER BY last_message_at DESC NULLS LAST
        LIMIT 50
        """, (pid, pid), default=[]
    )
    return render_template("messages/inbox.html",
                           profile=profile,
                           conversations=conversations,
                           active_tab="inbox")

@inbox_bp.route("/new")
def inbox_new():
    profile = _profile()
    if not profile:
        return render_template("auth/login.html", error="Please log in.")
    return render_template("messages/inbox.html",
                           profile=profile,
                           conversations=[],
                           active_tab="new")

@inbox_bp.route("/sent")
def inbox_sent():
    profile = _profile()
    if not profile:
        return render_template("auth/login.html", error="Please log in.")
    pid = profile["id"]
    tn = _thread_name_expr("t")
    sent = fast_query(
        f"""
        SELECT
          t.id,
          COALESCE({tn}, '') AS display_name,
          (SELECT m.body FROM chain_messages m
           WHERE m.thread_id = t.id AND m.sender_profile_id = %s
           ORDER BY m.created_at DESC LIMIT 1) AS last_message,
          (SELECT MAX(m.created_at) FROM chain_messages m
           WHERE m.thread_id = t.id AND m.sender_profile_id = %s) AS last_message_at
        FROM chain_message_threads t
        JOIN chain_thread_members tm ON tm.thread_id = t.id
        WHERE tm.profile_id = %s
          AND t.deleted_at IS NULL
          AND EXISTS (
            SELECT 1 FROM chain_messages m
            WHERE m.thread_id = t.id AND m.sender_profile_id = %s
          )
        ORDER BY last_message_at DESC NULLS LAST
        LIMIT 50
        """, (pid, pid, pid, pid), default=[]
    )
    return render_template("messages/inbox.html",
                           profile=profile,
                           conversations=sent,
                           active_tab="sent")

@inbox_bp.route("/blocked")
def inbox_blocked():
    profile = _profile()
    if not profile:
        return render_template("auth/login.html", error="Please log in.")
    pid = profile["id"]
    blocked = fast_query(
        """
        SELECT
          b.id, b.created_at,
          p.id AS profile_id, p.username, p.full_name AS display_name
        FROM chain_blocks b
        JOIN chain_profiles p ON p.id = b.blocked_profile_id
        WHERE b.blocker_profile_id = %s AND b.deleted_at IS NULL
        ORDER BY b.created_at DESC
        LIMIT 50
        """, (pid,), default=[]
    )
    return render_template("messages/inbox.html",
                           profile=profile,
                           conversations=blocked,
                           active_tab="blocked")
