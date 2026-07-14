import os
import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template, request, session, send_from_directory, url_for
from werkzeug.utils import secure_filename

from services.profile_service import get_current_profile
from services.support_service import (
    CATEGORIES, STATUSES, PRIORITIES,
    create_ticket, get_ticket, list_user_tickets, add_message, add_user_message, add_agent_message,
    get_messages, get_user_messages,
    update_ticket_status, assign_ticket, is_agent, list_all_tickets,
    count_tickets, get_ticket_events, get_help_articles, get_help_article,
    get_faq_categories, add_feedback, get_agent_stats, get_dashboard_stats,
    get_agent_assignments, _log_event,
)
from services.logging_service import log_error

support_bp = Blueprint("support", __name__, url_prefix="/api/support")
support_page_bp = Blueprint("support_pages", __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads", "support")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def _profile_id():
    p = get_current_profile()
    return (p or {}).get("id")

def _profile():
    return get_current_profile()

def _json_ok(data=None):
    return jsonify({"ok": True, **(data or {})})

def _json_error(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code

# ─── USER-FACING PAGES ─────────────────────────────────────

@support_page_bp.route("/support")
def support_center():
    profile = _profile()
    categories = CATEGORIES
    tickets = []
    if profile and profile.get("id"):
        tickets = list_user_tickets(profile["id"], limit=5)
    articles = get_help_articles(limit=6)
    return render_template("support/support_center.html", profile=profile, categories=categories, tickets=tickets, articles=articles)

@support_page_bp.route("/support/tickets")
def my_tickets():
    profile = _profile()
    if not profile or not profile.get("id"):
        return render_template("auth/login.html", next="/support/tickets")
    tickets = list_user_tickets(profile["id"])
    return render_template("support/my_tickets.html", profile=profile, tickets=tickets, statuses=STATUSES)

@support_page_bp.route("/support/new")
def new_ticket():
    profile = _profile()
    if not profile or not profile.get("id"):
        return render_template("auth/login.html", next="/support/new")
    category = request.args.get("category", "")
    related_profile = request.args.get("related_profile")
    related_post = request.args.get("related_post")
    related_order = request.args.get("related_order")
    related_transaction = request.args.get("related_transaction")
    return render_template("support/ticket_create.html", profile=profile, categories=CATEGORIES, selected_category=category, related_profile=related_profile, related_post=related_post, related_order=related_order, related_transaction=related_transaction)

@support_page_bp.route("/support/tickets/<ticket_id>")
def ticket_detail(ticket_id):
    profile = _profile()
    if not profile or not profile.get("id"):
        return render_template("auth/login.html", next=f"/support/tickets/{ticket_id}")
    ticket = get_ticket(ticket_id, profile["id"])
    if not ticket:
        return render_template("404.html"), 404
    messages = get_user_messages(ticket_id, profile["id"])
    events = get_ticket_events(ticket_id)
    return render_template("support/ticket_detail.html", profile=profile, ticket=ticket, messages=messages, events=events, categories=CATEGORIES)

@support_page_bp.route("/support/help")
def help_articles():
    profile = _profile()
    articles = get_help_articles()
    categories = get_faq_categories()
    return render_template("support/help_articles.html", profile=profile, articles=articles, categories=categories)

@support_page_bp.route("/support/help/<slug>")
def help_article_detail(slug):
    profile = _profile()
    article = get_help_article(slug)
    if not article:
        return render_template("404.html"), 404
    return render_template("support/help_article.html", profile=profile, article=article)

# ─── USER API ─────────────────────────────────────────────

@support_bp.route("/tickets", methods=["POST"])
def api_create_ticket():
    pid = _profile_id()
    if not pid:
        return _json_error("Not authenticated", 401)
    data = request.get_json(silent=True) or request.form
    subject = (data.get("subject") or "").strip()
    category = (data.get("category") or "").strip()
    description = (data.get("description") or "").strip()
    if not subject or not category or not description:
        return _json_error("Subject, category, and description are required")
    if category not in CATEGORIES:
        return _json_error("Invalid category")
    priority = data.get("priority", "medium")
    if priority not in PRIORITIES:
        priority = "medium"
    evidence = data.get("evidence_json")
    if isinstance(evidence, dict) or isinstance(evidence, list):
        import json as json_mod
        evidence = json_mod.dumps(evidence)
    ticket_id, err = create_ticket(
        profile_id=pid, subject=subject, category=category,
        description=description, priority=priority,
        related_profile_id=data.get("related_profile_id"),
        related_post_id=data.get("related_post_id"),
        related_reel_id=data.get("related_reel_id"),
        related_story_id=data.get("related_story_id"),
        related_live_room_id=data.get("related_live_room_id"),
        related_message_id=data.get("related_message_id"),
        related_call_id=data.get("related_call_id"),
        related_order_id=data.get("related_order_id"),
        related_transaction_id=data.get("related_transaction_id"),
        evidence_json=evidence,
    )
    if err:
        return _json_error(err, 500)
    return _json_ok({"ticket_id": ticket_id})

@support_bp.route("/tickets", methods=["GET"])
def api_list_tickets():
    pid = _profile_id()
    if not pid:
        return _json_error("Not authenticated", 401)
    status = request.args.get("status") or None
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = int(request.args.get("offset", 0))
    tickets = list_user_tickets(pid, status=status, limit=limit, offset=offset)
    return _json_ok({"tickets": tickets})

@support_bp.route("/tickets/<ticket_id>", methods=["GET"])
def api_get_ticket(ticket_id):
    pid = _profile_id()
    if not pid:
        return _json_error("Not authenticated", 401)
    ticket = get_ticket(ticket_id, pid)
    if not ticket:
        return _json_error("Ticket not found", 404)
    return _json_ok({"ticket": ticket})

@support_bp.route("/tickets/<ticket_id>/messages", methods=["GET"])
def api_get_messages(ticket_id):
    pid = _profile_id()
    if not pid:
        return _json_error("Not authenticated", 401)
    msgs = get_user_messages(ticket_id, pid)
    return _json_ok({"messages": msgs})

@support_bp.route("/tickets/<ticket_id>/messages", methods=["POST"])
def api_add_message(ticket_id):
    pid = _profile_id()
    if not pid:
        return _json_error("Not authenticated", 401)
    data = request.get_json(silent=True) or request.form
    message = (data.get("message") or "").strip()
    if not message:
        return _json_error("Message is required")
    result, err = add_user_message(ticket_id, pid, message)
    if err:
        if err == "ticket_not_found":
            return _json_error("Ticket not found", 404)
        if err == "ticket_not_active":
            return _json_error("Ticket is not active", 400)
        return _json_error(err, 500)
    return _json_ok({"success": True})

@support_bp.route("/tickets/<ticket_id>/feedback", methods=["POST"])
def api_submit_feedback(ticket_id):
    pid = _profile_id()
    if not pid:
        return _json_error("Not authenticated", 401)
    data = request.get_json(silent=True) or request.form
    rating = int(data.get("rating", 0))
    comment = data.get("comment", "")
    result, err = add_feedback(ticket_id, pid, rating, comment)
    if err:
        return _json_error(err, 400)
    return _json_ok({"success": True})

@support_bp.route("/tickets/<ticket_id>/reopen", methods=["POST"])
def api_reopen_ticket(ticket_id):
    pid = _profile_id()
    if not pid:
        return _json_error("Not authenticated", 401)
    ticket = get_ticket(ticket_id, pid)
    if not ticket:
        return _json_error("Ticket not found", 404)
    if ticket["status"] not in ("resolved", "closed", "rejected"):
        return _json_error("Ticket cannot be reopened")
    success, err = update_ticket_status(ticket_id, "appealed", pid, "User reopened ticket")
    if err:
        return _json_error(err, 500)
    return _json_ok({"success": True})

# ─── FILE UPLOAD ──────────────────────────────────────────

@support_bp.route("/tickets/<ticket_id>/upload", methods=["POST"])
def api_upload_attachment(ticket_id):
    pid = _profile_id()
    if not pid:
        return _json_error("Not authenticated", 401)
    ticket = get_ticket(ticket_id, pid)
    if not ticket:
        return _json_error("Ticket not found", 404)
    if "file" not in request.files:
        return _json_error("No file provided")
    file = request.files["file"]
    if not file.filename:
        return _json_error("No file selected")
    from services.storage_service import upload_support_attachment
    try:
        result = upload_support_attachment(file, ticket["id"], pid)
        return _json_ok({"attachment": result})
    except Exception as e:
        return _json_error(str(e), 500)

# ─── HELP ARTICLES API ────────────────────────────────────

@support_bp.route("/help/articles", methods=["GET"])
def api_help_articles():
    category = request.args.get("category")
    articles = get_help_articles(category_slug=category)
    return _json_ok({"articles": articles})

@support_bp.route("/help/categories", methods=["GET"])
def api_help_categories():
    cats = get_faq_categories()
    return _json_ok({"categories": cats})

# ─── ADMIN/AGENT API ──────────────────────────────────────

@support_bp.route("/admin/tickets", methods=["GET"])
def api_admin_list_tickets():
    pid = _profile_id()
    if not pid:
        return _json_error("Not authenticated", 401)
    agent = is_agent(pid)
    if not agent:
        return _json_error("Not authorized", 403)
    status = request.args.get("status") or None
    category = request.args.get("category") or None
    priority = request.args.get("priority") or None
    assigned_to = request.args.get("assigned_to") or None
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))
    tickets = list_all_tickets(status=status, category=category, priority=priority, assigned_to=assigned_to, limit=limit, offset=offset)
    total = count_tickets(status=status, category=category, priority=priority)
    return _json_ok({"tickets": tickets, "total": total})

@support_bp.route("/admin/tickets/<ticket_id>", methods=["GET"])
def api_admin_get_ticket(ticket_id):
    pid = _profile_id()
    if not pid:
        return _json_error("Not authenticated", 401)
    if not is_agent(pid):
        return _json_error("Not authorized", 403)
    ticket = get_ticket(ticket_id)
    if not ticket:
        return _json_error("Ticket not found", 404)
    msgs = get_messages(ticket_id)
    events = get_ticket_events(ticket_id)
    return _json_ok({"ticket": ticket, "messages": msgs, "events": events})

@support_bp.route("/admin/tickets/<ticket_id>/status", methods=["POST"])
def api_admin_update_status(ticket_id):
    pid = _profile_id()
    if not pid:
        return _json_error("Not authenticated", 401)
    agent = is_agent(pid)
    if not agent:
        return _json_error("Not authorized", 403)
    data = request.get_json(silent=True) or request.form
    new_status = (data.get("status") or "").strip()
    reason = (data.get("reason") or "").strip()
    if new_status not in STATUSES:
        return _json_error("Invalid status")
    success, err = update_ticket_status(ticket_id, new_status, pid, reason)
    if err:
        return _json_error(err, 500)
    return _json_ok({"success": True})

@support_bp.route("/admin/tickets/<ticket_id>/assign", methods=["POST"])
def api_admin_assign_ticket(ticket_id):
    pid = _profile_id()
    if not pid:
        return _json_error("Not authenticated", 401)
    agent = is_agent(pid)
    if not agent:
        return _json_error("Not authorized", 403)
    data = request.get_json(silent=True) or request.form
    target_profile_id = data.get("agent_profile_id")
    reason = data.get("reason", "")
    if not target_profile_id:
        return _json_error("Agent profile ID required")
    target_agent = is_agent(int(target_profile_id))
    if not target_agent:
        return _json_error("Target is not an active agent")
    success, err = assign_ticket(ticket_id, int(target_profile_id), pid, reason)
    if err:
        return _json_error(err, 500)
    return _json_ok({"success": True})

@support_bp.route("/admin/tickets/<ticket_id>/message", methods=["POST"])
def api_admin_add_message(ticket_id):
    pid = _profile_id()
    if not pid:
        return _json_error("Not authenticated", 401)
    agent = is_agent(pid)
    if not agent:
        return _json_error("Not authorized", 403)
    data = request.get_json(silent=True) or request.form
    message = (data.get("message") or "").strip()
    is_internal = data.get("is_internal", False)
    if not message:
        return _json_error("Message is required")
    result, err = add_message(ticket_id, pid, message, is_agent=True, is_internal_note=bool(is_internal))
    if err:
        return _json_error(err, 500)
    return _json_ok({"success": True})

@support_bp.route("/admin/stats", methods=["GET"])
def api_admin_stats():
    pid = _profile_id()
    if not pid:
        return _json_error("Not authenticated", 401)
    agent = is_agent(pid)
    if not agent:
        return _json_error("Not authorized", 403)
    stats = get_agent_stats(agent["id"])
    return _json_ok({"stats": stats})

@support_bp.route("/admin/dashboard", methods=["GET"])
def api_admin_dashboard():
    pid = _profile_id()
    if not pid:
        return _json_error("Not authenticated", 401)
    if not is_agent(pid):
        return _json_error("Not authorized", 403)
    stats = get_dashboard_stats()
    my_assignments = get_agent_assignments(is_agent(pid)["id"], limit=10) if is_agent(pid) else []
    return _json_ok({"stats": stats, "my_assignments": my_assignments})

@support_bp.route("/admin/agents", methods=["GET"])
def api_admin_agents():
    pid = _profile_id()
    if not pid:
        return _json_error("Not authenticated", 401)
    if not is_agent(pid):
        return _json_error("Not authorized", 403)
    from services.neon_service import fetch_all
    rows = fetch_all(
        """SELECT a.*, p.username, p.avatar_url, p.display_name
           FROM chain_support_agents a
           JOIN chain_profiles p ON a.profile_id=p.id
           ORDER BY a.is_active DESC, a.assigned_count ASC""",
        timeout_ms=5000,
    )
    return _json_ok({"agents": [dict(r) for r in (rows or [])]})

@support_bp.route("/admin/tickets/<ticket_id>/events", methods=["GET"])
def api_admin_events(ticket_id):
    pid = _profile_id()
    if not pid:
        return _json_error("Not authenticated", 401)
    if not is_agent(pid):
        return _json_error("Not authorized", 403)
    events = get_ticket_events(ticket_id)
    return _json_ok({"events": events})

# ─── ADMIN PAGE ────────────────────────────────────────────

@support_page_bp.route("/admin/support")
def admin_support_dashboard():
    profile = _profile()
    if not profile or not profile.get("id"):
        return render_template("auth/login.html", next="/admin/support")
    agent = is_agent(profile["id"])
    if not agent:
        return render_template("404.html"), 404
    stats = get_agent_stats(agent["id"])
    return render_template("admin/support_dashboard.html", profile=profile, agent=agent, stats=stats, categories=CATEGORIES, statuses=STATUSES)

@support_page_bp.route("/admin/support/tickets/<ticket_id>")
def admin_ticket_detail(ticket_id):
    profile = _profile()
    if not profile or not profile.get("id"):
        return render_template("auth/login.html", next=f"/admin/support/tickets/{ticket_id}")
    agent = is_agent(profile["id"])
    if not agent:
        return render_template("404.html"), 404
    ticket = get_ticket(ticket_id)
    if not ticket:
        return render_template("404.html"), 404
    messages = get_messages(ticket_id)
    events = get_ticket_events(ticket_id)
    return render_template("admin/support_ticket_detail.html", profile=profile, agent=agent, ticket=ticket, messages=messages, events=events, categories=CATEGORIES, statuses=STATUSES)
