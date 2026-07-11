import re


PROHIBITED_FIELDS = {
    "password", "passcode", "pin", "token", "access_token", "refresh_token",
    "secret", "api_key", "authorization", "cookie", "session", "email",
    "phone", "mobile", "national_id", "passport", "driver_license",
    "bank_account", "card_number", "cvv", "wallet_key", "private_key",
    "exact_location", "latitude", "longitude",
}
TEXT_LIMIT = 4000
LIST_LIMIT = 50
DICT_LIMIT = 50


def _normalize_key(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _is_prohibited_key(key):
    normalized = _normalize_key(key)
    for field in PROHIBITED_FIELDS:
        if _normalize_key(field) in normalized:
            return True
    return False


def redact_sensitive_text(text):
    value = str(text or "")
    value = value[:TEXT_LIMIT]
    value = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", "[redacted-email]", value, flags=re.I)
    value = re.sub(r"\b(?:\+?\d[\d\-\s]{6,}\d)\b", "[redacted-phone]", value)
    return value


def sanitize_metadata(metadata):
    return _sanitize_value(metadata, depth=0)


def _sanitize_value(value, depth=0):
    if depth > 4:
        return str(value)[:200]
    if isinstance(value, dict):
        cleaned = {}
        count = 0
        for key, item in value.items():
            if count >= DICT_LIMIT:
                break
            if _is_prohibited_key(key):
                continue
            cleaned[str(key)[:120]] = _sanitize_value(item, depth + 1)
            count += 1
        return cleaned
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_value(item, depth + 1) for item in list(value)[:LIST_LIMIT]]
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:200]


def contains_prohibited_sensitive_fields(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            if _is_prohibited_key(key):
                return True
            if contains_prohibited_sensitive_fields(value):
                return True
    elif isinstance(payload, (list, tuple, set)):
        return any(contains_prohibited_sensitive_fields(item) for item in payload)
    return False


def validate_external_ai_payload(payload):
    if contains_prohibited_sensitive_fields(payload):
        raise ValueError("unsafe_external_ai_payload")
    sanitized = sanitize_metadata(payload)
    if contains_prohibited_sensitive_fields(sanitized):
        raise ValueError("unsafe_external_ai_payload")
    return sanitized
