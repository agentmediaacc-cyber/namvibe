import os
import re
from uuid import uuid4
from datetime import datetime, timezone

from services.neon_service import fast_query, write_query, get_pool_status

_FAKE_SPAM_EVENTS = []
_RECENT_CONTENT = {}

SUSPICIOUS_WORDS = {"airdrop", "investment", "forex", "crypto", "loan", "jackpot", "winner", "free money"}
SCAM_PHRASES = {"send money", "click this link", "guaranteed profit", "double your money", "urgent payment", "verify your wallet"}
PAYMENT_WORDS = {"bank transfer", "cashapp", "western union", "gift card", "wallet unlock", "payout code"}


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1" or os.getenv("CHAIN_TEST_FAKE_DB") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _now():
    return datetime.now(timezone.utc).isoformat()


def analyze_text_for_spam(text):
    text = text or ""
    lowered = text.lower()
    reasons = []
    score = 0
    links = re.findall(r"https?://|www\.", lowered)
    if len(links) >= 2:
        score += 30
        reasons.append("too_many_links")
    elif links:
        score += 10
        reasons.append("contains_link")
    for word in SUSPICIOUS_WORDS:
        if word in lowered:
            score += 10
            reasons.append(f"suspicious_word:{word}")
    for phrase in SCAM_PHRASES:
        if phrase in lowered:
            score += 20
            reasons.append(f"scam_phrase:{phrase}")
    for word in PAYMENT_WORDS:
        if word in lowered:
            score += 15
            reasons.append(f"payment_keyword:{word}")
    emoji_count = len(re.findall(r"[\U0001F300-\U0001FAFF]", text))
    if emoji_count >= 8:
        score += 15
        reasons.append("excessive_emojis")
    if len(text) > 20 and len(set(text.split())) <= 3:
        score += 10
        reasons.append("low_word_variety")
    score = min(100, score)
    return {"ok": True, "spam": score >= 50, "score": score, "reasons": reasons}


def check_link_risk(text):
    result = analyze_text_for_spam(text)
    return {"ok": True, "risky": any("link" in r for r in result["reasons"]), "score": result["score"], "reasons": result["reasons"]}


def check_repeated_content(profile_id, content):
    normalized = re.sub(r"\s+", " ", (content or "").strip().lower())
    if not normalized:
        return {"ok": True, "repeated": False, "score": 0, "reasons": []}
    recent = _RECENT_CONTENT.setdefault(profile_id or "anonymous", [])
    repeats = recent.count(normalized)
    recent.append(normalized)
    _RECENT_CONTENT[profile_id or "anonymous"] = recent[-20:]
    score = min(100, repeats * 30)
    return {"ok": True, "repeated": repeats >= 2, "score": score, "reasons": ["repeated_content"] if repeats >= 2 else []}


def analyze_message_frequency(profile_id, window_seconds=60):
    events = [e for e in _FAKE_SPAM_EVENTS if e.get("profile_id") == profile_id and e.get("event_type") == "message_sent"]
    count = len(events[-20:])
    score = 80 if count >= 12 else 40 if count >= 8 else 0
    return {"ok": True, "rapid": score >= 40, "score": score, "count": count, "reasons": ["rapid_send_frequency"] if score else []}


def check_mass_messaging(profile_id, recipient_count=0):
    score = 80 if recipient_count >= 20 else 45 if recipient_count >= 10 else 0
    return {"ok": True, "mass_messaging": score >= 45, "score": score, "reasons": ["mass_messaging"] if score else []}


def record_spam_event(profile_id, event_type, score=0, content_type=None, content_id=None, metadata=None):
    event = {"id": str(uuid4()), "profile_id": profile_id, "event_type": event_type, "score": int(score or 0), "content_type": content_type, "content_id": content_id, "metadata": metadata or {}, "created_at": _now()}
    _FAKE_SPAM_EVENTS.append(event)
    if _db_available():
        try:
            import json
            write_query(
                "INSERT INTO chain_spam_events (id, profile_id, event_type, score, content_type, content_id, metadata) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)",
                (event["id"], profile_id, event_type, event["score"], content_type, content_id, json.dumps(metadata or {}))
            )
        except Exception:
            pass
    return {"ok": True, "event": event}


def is_spammy_message(profile_id, text):
    text_result = analyze_text_for_spam(text)
    repeat = check_repeated_content(profile_id, text)
    score = min(100, text_result["score"] + repeat["score"])
    reasons = text_result["reasons"] + repeat["reasons"]
    if score >= 50:
        record_spam_event(profile_id, "message_spam_detected", score, "message", metadata={"reasons": reasons})
    return {"ok": True, "spam": score >= 50, "score": score, "reasons": reasons}


def get_spam_summary(profile_id=None):
    events = [e for e in _FAKE_SPAM_EVENTS if not profile_id or e.get("profile_id") == profile_id]
    return {"ok": True, "events": events[-100:], "count": len(events), "max_score": max([e["score"] for e in events], default=0)}
