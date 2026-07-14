"""Connecting You — NamVibe Dating Program Routes"""

from flask import Blueprint, request, jsonify, render_template, redirect, session
from services.connecting_you_service import (
    enroll, get_enrollment, update_enrollment_status, list_enrollments,
    get_assessment_questions, submit_assessment, get_assessment_responses,
    find_top_matches, calculate_pair_compatibility,
    create_introduction, respond_to_introduction, get_introductions,
    get_matches, get_match_stats,
    list_events, get_event, register_for_event, create_event,
    pop_balloon, express_interest,
    submit_success_story, get_success_stories,
    list_mentors, get_admin_stats,
    list_all_mentors, create_mentor, toggle_mentor,
    create_announcement, list_announcements,
    list_events_admin, update_event_status,
    NAMIBIA_REGIONS,
)
from services.profile_service import get_current_profile
from api_routes.profile_routes import login_required

cy_bp = Blueprint("connecting_you", __name__, url_prefix="/dating/connecting-you")

def _pid():
    p = get_current_profile()
    return p["id"] if p and p.get("id") else None


# ─── PAGE: Program Home ───────────────────────────────────

@cy_bp.route("/")
def cy_home():
    profile = get_current_profile()
    pid = profile["id"] if profile else None
    enrollment = get_enrollment(pid) if pid else None
    stories = get_success_stories(featured_only=True, limit=6)
    events = list_events(limit=6)
    stats = get_match_stats()
    mentors = list_mentors()
    return render_template(
        "connecting_you/index.html",
        profile=profile,
        enrollment=enrollment,
        stories=stories,
        events=events,
        stats=stats,
        mentors=mentors,
        regions=NAMIBIA_REGIONS,
    )


# ─── PAGE: Enrollment ─────────────────────────────────────

@cy_bp.route("/enroll", methods=["GET", "POST"])
@login_required
def cy_enroll_page():
    profile = get_current_profile()
    pid = profile["id"] if profile else None
    enrollment = get_enrollment(pid) if pid else None

    if request.method == "POST":
        data = request.get_json() or request.form.to_dict()
        result = enroll(pid, data)
        return jsonify(result) if request.is_json else redirect("/dating/connecting-you/")

    return render_template(
        "connecting_you/enroll.html",
        profile=profile,
        enrollment=enrollment,
        regions=NAMIBIA_REGIONS,
    )


# ─── PAGE: Assessment ─────────────────────────────────────

@cy_bp.route("/assessment", methods=["GET", "POST"])
@login_required
def cy_assessment_page():
    profile = get_current_profile()
    pid = profile["id"] if profile else None
    enrollment = get_enrollment(pid) if pid else None
    questions = get_assessment_questions()
    responses = get_assessment_responses(pid) if pid else []

    if request.method == "POST":
        data = request.get_json() or {}
        answers = data.get("answers", [])
        result = submit_assessment(pid, answers)
        return jsonify(result)

    return render_template(
        "connecting_you/assessment.html",
        profile=profile,
        enrollment=enrollment,
        questions=questions,
        responses=responses,
    )


# ─── PAGE: Matches ────────────────────────────────────────

@cy_bp.route("/matches")
@login_required
def cy_matches_page():
    profile = get_current_profile()
    pid = profile["id"] if profile else None
    matches = get_matches(pid) if pid else []
    introductions = get_introductions(pid) if pid else []
    return render_template(
        "connecting_you/matches.html",
        profile=profile,
        matches=matches,
        introductions=introductions,
    )


# ─── PAGE: Browse ─────────────────────────────────────────

@cy_bp.route("/browse")
@login_required
def cy_browse_page():
    profile = get_current_profile()
    pid = profile["id"] if profile else None
    matches = find_top_matches(pid, limit=12) if pid else []
    return render_template(
        "connecting_you/browse.html",
        profile=profile,
        matches=matches,
    )


# ─── PAGE: Events ─────────────────────────────────────────

@cy_bp.route("/events")
def cy_events_page():
    profile = get_current_profile()
    event_type = request.args.get("type", "")
    events = list_events(event_type=event_type if event_type else None)
    return render_template(
        "connecting_you/events.html",
        profile=profile,
        events=events,
        selected_type=event_type,
    )


@cy_bp.route("/events/<event_id>")
def cy_event_detail(event_id):
    profile = get_current_profile()
    event = get_event(event_id)
    if not event:
        return render_template("connecting_you/index.html", profile=profile, error="Event not found"), 404
    return render_template(
        "connecting_you/event_detail.html",
        profile=profile,
        event=event,
    )


@cy_bp.route("/events/<event_id>/register", methods=["POST"])
@login_required
def cy_event_register(event_id):
    pid = _pid()
    result = register_for_event(event_id, pid)
    return jsonify(result)


# ─── PAGE: Success Stories ────────────────────────────────

@cy_bp.route("/stories")
def cy_stories_page():
    profile = get_current_profile()
    stories = get_success_stories(limit=20)
    return render_template(
        "connecting_you/stories.html",
        profile=profile,
        stories=stories,
    )


@cy_bp.route("/stories/submit", methods=["GET", "POST"])
@login_required
def cy_story_submit():
    profile = get_current_profile()
    pid = profile["id"] if profile else None
    if request.method == "POST":
        data = request.get_json() or request.form.to_dict()
        data["submitted_by"] = pid
        result = submit_success_story(data)
        return jsonify(result) if request.is_json else redirect("/dating/connecting-you/stories")
    return render_template("connecting_you/story_submit.html", profile=profile)


# ─── API ──────────────────────────────────────────────────

@cy_bp.route("/api/enroll", methods=["POST"])
@login_required
def api_enroll():
    pid = _pid()
    data = request.get_json() or {}
    return jsonify(enroll(pid, data))


@cy_bp.route("/api/enrollment")
@login_required
def api_enrollment():
    pid = _pid()
    e = get_enrollment(pid)
    return jsonify({"enrollment": e})


@cy_bp.route("/api/assessment/questions")
def api_assessment_questions():
    return jsonify({"questions": get_assessment_questions()})


@cy_bp.route("/api/assessment/submit", methods=["POST"])
@login_required
def api_assessment_submit():
    pid = _pid()
    data = request.get_json() or {}
    return jsonify(submit_assessment(pid, data.get("answers", [])))


@cy_bp.route("/api/matches")
@login_required
def api_matches():
    pid = _pid()
    return jsonify({"matches": get_matches(pid)})


@cy_bp.route("/api/browse")
@login_required
def api_browse():
    pid = _pid()
    return jsonify({"matches": find_top_matches(pid, limit=12)})


@cy_bp.route("/api/introductions")
@login_required
def api_introductions():
    pid = _pid()
    return jsonify({"introductions": get_introductions(pid)})


@cy_bp.route("/api/introductions/<intro_id>/respond", methods=["POST"])
@login_required
def api_respond_intro(intro_id):
    pid = _pid()
    data = request.get_json() or {}
    response = data.get("response", "")
    if response not in ("accept", "decline", "maybe"):
        return jsonify({"ok": False, "error": "Invalid response"}), 400
    return jsonify(respond_to_introduction(pid, intro_id, response))


@cy_bp.route("/api/events")
def api_events():
    event_type = request.args.get("type", "")
    return jsonify({"events": list_events(event_type=event_type if event_type else None)})


@cy_bp.route("/api/events/<event_id>/register", methods=["POST"])
@login_required
def api_event_register(event_id):
    pid = _pid()
    return jsonify(register_for_event(event_id, pid))


@cy_bp.route("/api/events/<event_id>/pop-balloon", methods=["POST"])
@login_required
def api_pop_balloon(event_id):
    pid = _pid()
    return jsonify(pop_balloon(event_id, pid))


@cy_bp.route("/api/balloon/<pop_id>/interest", methods=["POST"])
@login_required
def api_balloon_interest(pop_id):
    pid = _pid()
    return jsonify(express_interest(pop_id, pid))


@cy_bp.route("/api/stories")
def api_stories():
    return jsonify({"stories": get_success_stories(limit=20)})


@cy_bp.route("/api/mentors")
def api_mentors():
    return jsonify({"mentors": list_mentors()})


@cy_bp.route("/api/stats")
def api_stats():
    return jsonify(get_match_stats())


@cy_bp.route("/api/compatibility/<target_id>")
@login_required
def api_compatibility(target_id):
    pid = _pid()
    score, categories = calculate_pair_compatibility(pid, target_id)
    return jsonify({"overall": score, "categories": categories})


# ─── ADMIN API ────────────────────────────────────────────

cy_admin_bp = Blueprint("connecting_you_admin", __name__, url_prefix="/dating/admin")


@cy_admin_bp.route("/")
@login_required
def cy_admin_dashboard():
    profile = get_current_profile()
    if not profile or not profile.get("is_admin"):
        return redirect("/dating/connecting-you/")
    stats = get_admin_stats()
    pending = list_enrollments(status="pending", limit=50)
    return render_template(
        "connecting_you/admin_dashboard.html",
        profile=profile,
        stats=stats,
        pending=pending,
        regions=NAMIBIA_REGIONS,
    )


@cy_admin_bp.route("/api/enrollments")
@login_required
def api_admin_enrollments():
    profile = get_current_profile()
    if not profile or not profile.get("is_admin"):
        return jsonify({"ok": False}), 403
    status = request.args.get("status", "")
    region = request.args.get("region", "")
    return jsonify({"enrollments": list_enrollments(status=status or None, region=region or None)})


@cy_admin_bp.route("/api/enrollments/<profile_id>/approve", methods=["POST"])
@login_required
def api_admin_approve(profile_id):
    profile = get_current_profile()
    if not profile or not profile.get("is_admin"):
        return jsonify({"ok": False}), 403
    return jsonify(update_enrollment_status(profile_id, "active", verified=True))


@cy_admin_bp.route("/api/enrollments/<profile_id>/suspend", methods=["POST"])
@login_required
def api_admin_suspend(profile_id):
    profile = get_current_profile()
    if not profile or not profile.get("is_admin"):
        return jsonify({"ok": False}), 403
    return jsonify(update_enrollment_status(profile_id, "suspended"))


@cy_admin_bp.route("/api/introductions/create", methods=["POST"])
@login_required
def api_admin_create_intro():
    profile = get_current_profile()
    if not profile or not profile.get("is_admin"):
        return jsonify({"ok": False}), 403
    data = request.get_json() or {}
    return jsonify(create_introduction(
        data.get("profile_a"), data.get("profile_b"),
        admin_id=profile["id"], notes=data.get("notes", "")
    ))


@cy_admin_bp.route("/api/events/create", methods=["POST"])
@login_required
def api_admin_create_event():
    profile = get_current_profile()
    if not profile or not profile.get("is_admin"):
        return jsonify({"ok": False}), 403
    data = request.get_json() or {}
    return jsonify(create_event(data))


@cy_admin_bp.route("/api/stats")
@login_required
def api_admin_stats():
    profile = get_current_profile()
    if not profile or not profile.get("is_admin"):
        return jsonify({"ok": False}), 403
    return jsonify(get_admin_stats())


@cy_admin_bp.route("/api/mentors")
@login_required
def api_admin_mentors():
    profile = get_current_profile()
    if not profile or not profile.get("is_admin"):
        return jsonify({"ok": False}), 403
    return jsonify({"mentors": list_all_mentors()})


@cy_admin_bp.route("/api/mentors/create", methods=["POST"])
@login_required
def api_admin_create_mentor():
    profile = get_current_profile()
    if not profile or not profile.get("is_admin"):
        return jsonify({"ok": False}), 403
    data = request.get_json() or {}
    return jsonify(create_mentor(data))


@cy_admin_bp.route("/api/mentors/<int:mentor_id>/toggle", methods=["POST"])
@login_required
def api_admin_toggle_mentor(mentor_id):
    profile = get_current_profile()
    if not profile or not profile.get("is_admin"):
        return jsonify({"ok": False}), 403
    data = request.get_json() or {}
    return jsonify(toggle_mentor(mentor_id, data.get("is_active", True)))


@cy_admin_bp.route("/api/announcements", methods=["GET", "POST"])
@login_required
def api_admin_announcements():
    profile = get_current_profile()
    if not profile or not profile.get("is_admin"):
        return jsonify({"ok": False}), 403
    if request.method == "POST":
        data = request.get_json() or {}
        return jsonify(create_announcement(data))
    return jsonify({"announcements": list_announcements()})


@cy_admin_bp.route("/api/events")
@login_required
def api_admin_events():
    profile = get_current_profile()
    if not profile or not profile.get("is_admin"):
        return jsonify({"ok": False}), 403
    status = request.args.get("status", "")
    return jsonify({"events": list_events_admin(status=status or None)})


@cy_admin_bp.route("/api/events/<event_id>/status", methods=["POST"])
@login_required
def api_admin_update_event_status(event_id):
    profile = get_current_profile()
    if not profile or not profile.get("is_admin"):
        return jsonify({"ok": False}), 403
    data = request.get_json() or {}
    return jsonify(update_event_status(event_id, data.get("status", "scheduled")))


def register_connecting_you_routes(app):
    app.register_blueprint(cy_bp)
    app.register_blueprint(cy_admin_bp)
    print("[connecting-you] Dating program routes registered")
