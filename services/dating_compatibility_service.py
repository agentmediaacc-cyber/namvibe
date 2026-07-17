"""Deterministic, explainable compatibility scoring for NamVibe Dating."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List


def _as_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip().lower() for v in value if str(v).strip()]
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        if value.startswith("[") and value.endswith("]"):
            try:
                import json
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return _as_list(parsed)
            except Exception:
                pass
        return [part.strip().lower() for part in value.split(",") if part.strip()]
    return [str(value).strip().lower()]


def _age(row: Dict[str, Any]) -> int | None:
    for key in ("age",):
        raw = row.get(key)
        if raw not in (None, ""):
            try:
                age = int(raw)
                if 13 <= age <= 120:
                    return age
            except Exception:
                pass
    dob = row.get("date_of_birth")
    if not dob:
        return None
    try:
        if isinstance(dob, str):
            dob_dt = datetime.fromisoformat(dob.replace("Z", "+00:00"))
        else:
            dob_dt = dob
        now = datetime.now(timezone.utc)
        years = now.year - dob_dt.year - ((now.month, now.day) < (dob_dt.month, dob_dt.day))
        return years if 13 <= years <= 120 else None
    except Exception:
        return None


def _city(row: Dict[str, Any]) -> str:
    for key in ("town", "city", "current_location", "location", "region"):
        value = row.get(key)
        if value:
            return str(value).strip().lower()
    return ""


def _goal(row: Dict[str, Any]) -> str:
    return str(row.get("relationship_goal") or row.get("dating_intent") or "").strip().lower()


def _intent(row: Dict[str, Any]) -> str:
    return str(row.get("interested_in") or row.get("looking_for") or "").strip().lower()


def build_compatibility_profile(*, viewer, viewer_profile=None, target_profile=None, preferences=None) -> Dict[str, Any]:
    viewer_profile = viewer_profile or {}
    target_profile = target_profile or {}
    preferences = preferences or {}
    viewer_age = _age(viewer_profile)
    target_age = _age(target_profile)
    return {
        "viewer_id": str(viewer or ""),
        "viewer_profile": viewer_profile,
        "target_profile": target_profile,
        "preferences": preferences,
        "viewer_age": viewer_age,
        "target_age": target_age,
        "viewer_goal": _goal(viewer_profile),
        "target_goal": _goal(target_profile),
        "viewer_intent": _intent(preferences) or _intent(viewer_profile),
        "target_intent": _intent(target_profile),
        "viewer_interests": _as_list(viewer_profile.get("interests")),
        "target_interests": _as_list(target_profile.get("interests")),
        "viewer_languages": _as_list(viewer_profile.get("languages")),
        "target_languages": _as_list(target_profile.get("languages")),
        "viewer_city": _city(viewer_profile),
        "target_city": _city(target_profile),
        "viewer_complete": sum(1 for key in ("bio", "interests", "photos", "relationship_goal") if viewer_profile.get(key)),
        "target_complete": sum(1 for key in ("bio", "interests", "photos", "relationship_goal") if target_profile.get(key)),
    }


def score_compatibility(profile: Dict[str, Any]) -> Dict[str, Any]:
    score = 35
    reasons: List[str] = []
    confidence = 0.45
    missing = 0

    viewer_age = profile.get("viewer_age")
    target_age = profile.get("target_age")
    if viewer_age is None or target_age is None:
        missing += 1
    else:
        age_gap = abs(viewer_age - target_age)
        if age_gap <= 2:
            score += 18
            confidence += 0.12
            reasons.append("close age range")
        elif age_gap <= 5:
            score += 10
            confidence += 0.08
            reasons.append("compatible age range")
        elif age_gap <= 10:
            score += 4
            reasons.append("some age overlap")
        else:
            score -= 8

    viewer_goal = profile.get("viewer_goal")
    target_goal = profile.get("target_goal")
    if viewer_goal and target_goal:
        if viewer_goal == target_goal:
            score += 16
            confidence += 0.12
            reasons.append("same relationship goal")
        else:
            score += 2
    else:
        missing += 1

    viewer_intent = profile.get("viewer_intent")
    target_intent = profile.get("target_intent")
    if viewer_intent and target_intent:
        if viewer_intent == target_intent:
            score += 8
            confidence += 0.06
            reasons.append("aligned dating intent")
    else:
        missing += 1

    viewer_interests = set(profile.get("viewer_interests") or [])
    target_interests = set(profile.get("target_interests") or [])
    common_interests = sorted(viewer_interests & target_interests)
    if common_interests:
        score += min(len(common_interests) * 4, 16)
        confidence += min(len(common_interests) * 0.04, 0.12)
        reasons.append(f"shared interests: {', '.join(common_interests[:3])}")
    else:
        missing += 1

    viewer_languages = set(profile.get("viewer_languages") or [])
    target_languages = set(profile.get("target_languages") or [])
    common_languages = sorted(viewer_languages & target_languages)
    if common_languages:
        score += min(len(common_languages) * 3, 9)
        reasons.append(f"shared language: {', '.join(common_languages[:2])}")
    else:
        missing += 1

    viewer_city = profile.get("viewer_city")
    target_city = profile.get("target_city")
    if viewer_city and target_city and viewer_city == target_city:
        score += 8
        confidence += 0.06
        reasons.append(f"both in {target_city.title()}")
    elif viewer_city and target_city:
        score += 2
    else:
        missing += 1

    completeness = (profile.get("viewer_complete", 0) + profile.get("target_complete", 0)) / 8.0
    score += int(min(completeness, 1.0) * 6)
    confidence += min(completeness * 0.08, 0.08)

    score = max(0, min(100, score))
    confidence = max(0.0, min(1.0, confidence - min(missing * 0.05, 0.2)))
    if score < 45 and not reasons:
        reasons.append("new profile")
    if not reasons:
        reasons.append("new profile")

    return {
        "score": int(score),
        "reasons": reasons[:4],
        "confidence": round(confidence, 2),
        "missing_data_fields": missing,
        "has_strong_signals": bool(common_interests or common_languages or viewer_goal == target_goal),
    }
