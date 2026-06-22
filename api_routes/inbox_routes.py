"""Inbox routes — simplified messaging inbox with tabs."""
from flask import Blueprint, render_template, request
from services.profile_service import get_current_profile
from services.neon_service import fast_query

inbox_bp = Blueprint("inbox", __name__, url_prefix="/inbox")


def _profile():
    return get_current_profile()


@inbox_bp.route("/")
def inbox_main():
    profile = _profile()
    if not profile:
        return render_template("auth/login.html", error="Please log in.")
    pid = profile["id"]
    conversations = fast_query(
        """
        SELECT DISTINCT ON (t.id)
          t.id, t.title AS display_name,
          t.last_message, t.last_message_at, t.thread_type,
          CASE WHEN t.thread_type = 'direct' THEN
            (SELECT p.avatar_url FROM chain_thread_participants tp
             JOIN chain_profiles p ON p.id = tp.profile_id
             WHERE tp.thread_id = t.id AND tp.profile_id != %s LIMIT 1)
          ELSE NULL END AS avatar_url
        FROM chain_threads t
        JOIN chain_thread_participants tp ON tp.thread_id = t.id
        WHERE tp.profile_id = %s AND t.deleted_at IS NULL
          AND t.is_archived = FALSE
        ORDER BY t.id, t.last_message_at DESC NULLS LAST
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
    sent = fast_query(
        """
        SELECT DISTINCT ON (t.id)
          t.id, t.title AS display_name,
          m.content AS last_message, m.created_at AS last_message_at
        FROM chain_threads t
        JOIN chain_thread_participants tp ON tp.thread_id = t.id
        JOIN chain_messages m ON m.thread_id = t.id AND m.sender_id = %s
        WHERE tp.profile_id = %s AND t.deleted_at IS NULL
        ORDER BY t.id, m.created_at DESC NULLS LAST
        LIMIT 50
        """, (pid, pid), default=[]
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
          p.id AS profile_id, p.username, p.display_name
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
