from flask import Blueprint, jsonify, render_template, request

from api_routes.profile_routes import login_required
from services.ai.config import get_ai_config
from services.ai.feature_flags import is_ai_feature_enabled
from services.ai.interaction_service import (
    normalize_action_type,
    normalize_target_type,
    record_interaction,
    record_interactions_batch,
)
from services.ai.recommendation_service import (
    log_recommendation_impressions,
    recommend_posts,
    recommend_profiles,
    recommend_reels,
)
from services.ai.user_profile_service import (
    get_or_create_ai_user_profile,
    get_recommendation_context,
    update_explicit_interests,
    update_language_preferences,
)
from services.profile_service import get_current_profile
from services.rate_limit_service import limiter, user_or_ip_key
from services.redis_service import get_json, set_json


ai_bp = Blueprint("ai", __name__)


def _current_profile():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return None
    return profile


def _disabled_recommendation_response():
    return jsonify({
        "enabled": False,
        "items": [],
        "algorithm_version": get_ai_config().recommendation_version,
    })


@ai_bp.get("/ai/")
def ai_index():
    profile = get_current_profile()
    return render_template("ai/index.html", profile=profile)


@ai_bp.get("/api/ai/status")
def api_ai_status():
    config = get_ai_config()
    profile = _current_profile()
    profile_id = (profile or {}).get("id")
    cache_key = f"ai:status:{profile_id or 'anon'}"
    cached = get_json(cache_key)
    if isinstance(cached, dict):
        return jsonify(cached)
    if not profile_id:
        payload = {
            "ai_enabled": config.enabled,
            "external_provider_enabled": bool(config.external_calls_enabled and config.provider not in {"", "disabled"}),
            "interaction_tracking_enabled": False,
            "recommendations_enabled": False,
            "algorithm_version": config.recommendation_version,
            "provider": config.provider,
        }
        set_json(cache_key, payload, ttl=min(config.cache_ttl_seconds, 60))
        return jsonify(payload)
    payload = {
        "ai_enabled": config.enabled,
        "external_provider_enabled": bool(config.external_calls_enabled and config.provider not in {"", "disabled"}),
        "interaction_tracking_enabled": is_ai_feature_enabled("ai_interaction_tracking", profile_id=profile_id),
        "recommendations_enabled": is_ai_feature_enabled("ai_recommendations", profile_id=profile_id),
        "algorithm_version": config.recommendation_version,
        "provider": config.provider,
    }
    set_json(cache_key, payload, ttl=min(config.cache_ttl_seconds, 60))
    return jsonify(payload)


@ai_bp.post("/api/ai/interactions")
@login_required
@limiter.limit("120/minute", key_func=user_or_ip_key)
def api_ai_interaction():
    profile = _current_profile()
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    try:
        result = record_interaction(
            profile_id=profile["id"],
            target_type=normalize_target_type(data.get("target_type")),
            target_id=data.get("target_id"),
            action_type=normalize_action_type(data.get("action_type")),
            source_surface=data.get("source_surface"),
            session_id=data.get("session_id"),
            dwell_time_ms=data.get("dwell_time_ms"),
            metadata=data.get("metadata"),
        )
    except ValueError as error:
        return jsonify({"ok": False, "error": str(error)}), 400
    return jsonify({"ok": bool(result.get("ok")), "status": "accepted" if result.get("ok") else "skipped"}), 202


@ai_bp.post("/api/ai/interactions/batch")
@login_required
@limiter.limit("60/minute", key_func=user_or_ip_key)
def api_ai_interaction_batch():
    profile = _current_profile()
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    interactions = list(data.get("interactions") or [])
    if len(interactions) > 50:
        return jsonify({"ok": False, "error": "batch_too_large"}), 400
    try:
        results = record_interactions_batch(profile["id"], interactions)
    except ValueError as error:
        return jsonify({"ok": False, "error": str(error)}), 400
    return jsonify({"ok": True, "results": results}), 202


def _recommendation_response(kind, loader):
    profile = _current_profile()
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    if not is_ai_feature_enabled("ai_recommendations", profile_id=profile["id"]):
        return _disabled_recommendation_response()
    limit = min(max(request.args.get("limit", 20, type=int), 1), 50)
    offset = min(max(request.args.get("offset", 0, type=int), 0), 500)
    items = loader(profile["id"], limit=limit, offset=offset)
    request_id = request.headers.get("X-Request-ID") or request.args.get("request_id")
    log_recommendation_impressions(profile["id"], kind, items, request_id=request_id)
    return jsonify({
        "enabled": True,
        "items": items,
        "algorithm_version": get_ai_config().recommendation_version,
    })


@ai_bp.get("/api/ai/recommendations/profiles")
@login_required
def api_ai_recommend_profiles():
    return _recommendation_response("profiles", recommend_profiles)


@ai_bp.get("/api/ai/recommendations/posts")
@login_required
def api_ai_recommend_posts():
    return _recommendation_response("posts", recommend_posts)


@ai_bp.get("/api/ai/recommendations/reels")
@login_required
def api_ai_recommend_reels():
    return _recommendation_response("reels", recommend_reels)


@ai_bp.get("/api/ai/profile")
@login_required
def api_ai_profile():
    profile = _current_profile()
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    ai_profile = get_or_create_ai_user_profile(profile["id"]) or {}
    return jsonify({
        "profile_id": profile["id"],
        "explicit_interests": ai_profile.get("explicit_interests") or [],
        "inferred_interests": ai_profile.get("inferred_interests") or [],
        "preferred_languages": ai_profile.get("preferred_languages") or [],
        "preferred_content_types": ai_profile.get("preferred_content_types") or [],
        "recommendation_settings": ai_profile.get("recommendation_settings") or {},
        "onboarding_completed": bool(ai_profile.get("onboarding_completed")),
        "interaction_count": int(ai_profile.get("interaction_count") or 0),
    })


@ai_bp.patch("/api/ai/profile")
@login_required
@limiter.limit("30/minute", key_func=user_or_ip_key)
def api_ai_profile_update():
    profile = _current_profile()
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    ai_profile = get_or_create_ai_user_profile(profile["id"]) or {}
    if "explicit_interests" in data:
        ai_profile["explicit_interests"] = update_explicit_interests(profile["id"], data.get("explicit_interests"))
    if "preferred_languages" in data:
        ai_profile["preferred_languages"] = update_language_preferences(profile["id"], data.get("preferred_languages"))
    if "preferred_content_types" in data:
        values = data.get("preferred_content_types") or []
        if not isinstance(values, list) or len(values) > 20:
            return jsonify({"ok": False, "error": "invalid_preferred_content_types"}), 400
        from services.neon_service import execute
        from psycopg2.extras import Json
        execute(
            "UPDATE chain_ai_user_profiles SET preferred_content_types = %s::jsonb, updated_at = now() WHERE profile_id = %s",
            (Json([str(value)[:40].lower() for value in values[:20]]), profile["id"]),
            timeout_ms=2000,
        )
        ai_profile["preferred_content_types"] = [str(value)[:40].lower() for value in values[:20]]
    if "recommendation_settings" in data:
        settings = data.get("recommendation_settings")
        if not isinstance(settings, dict) or len(settings) > 20:
            return jsonify({"ok": False, "error": "invalid_recommendation_settings"}), 400
        from services.neon_service import execute
        from psycopg2.extras import Json
        execute(
            "UPDATE chain_ai_user_profiles SET recommendation_settings = %s::jsonb, updated_at = now() WHERE profile_id = %s",
            (Json(settings), profile["id"]),
            timeout_ms=2000,
        )
        ai_profile["recommendation_settings"] = settings
    context = get_recommendation_context(profile["id"])
    return jsonify({"ok": True, "profile": {
        "explicit_interests": context.get("explicit_interests") or [],
        "inferred_interests": context.get("inferred_interests") or [],
        "preferred_languages": context.get("preferred_languages") or [],
        "preferred_content_types": context.get("preferred_content_types") or [],
        "recommendation_settings": context.get("recommendation_settings") or {},
    }})
