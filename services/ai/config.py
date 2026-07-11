from dataclasses import dataclass
import os


def _parse_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(name, default, minimum=None, maximum=None):
    raw = os.getenv(name)
    try:
        value = int(str(raw).strip()) if raw not in (None, "") else int(default)
    except (TypeError, ValueError):
        value = int(default)
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


@dataclass(frozen=True)
class AIConfig:
    enabled: bool
    provider: str
    model: str
    api_key_present: bool
    base_url: str
    timeout_seconds: int
    max_retries: int
    recommendations_enabled: bool
    interaction_tracking_enabled: bool
    external_calls_enabled: bool
    log_provider_usage: bool
    cache_ttl_seconds: int
    recommendation_version: str


def get_ai_config():
    provider = (os.getenv("NAMVIBE_AI_PROVIDER") or "disabled").strip().lower() or "disabled"
    model = (os.getenv("NAMVIBE_AI_MODEL") or "").strip()
    base_url = (os.getenv("NAMVIBE_AI_BASE_URL") or "").strip()
    api_key_present = bool((os.getenv("NAMVIBE_AI_API_KEY") or "").strip())
    return AIConfig(
        enabled=_parse_bool("NAMVIBE_AI_ENABLED", False),
        provider=provider,
        model=model,
        api_key_present=api_key_present,
        base_url=base_url,
        timeout_seconds=_parse_int("NAMVIBE_AI_TIMEOUT_SECONDS", 12, minimum=1, maximum=30),
        max_retries=_parse_int("NAMVIBE_AI_MAX_RETRIES", 1, minimum=0, maximum=3),
        recommendations_enabled=_parse_bool("NAMVIBE_AI_RECOMMENDATIONS_ENABLED", False),
        interaction_tracking_enabled=_parse_bool("NAMVIBE_AI_INTERACTION_TRACKING_ENABLED", True),
        external_calls_enabled=_parse_bool("NAMVIBE_AI_EXTERNAL_CALLS_ENABLED", False),
        log_provider_usage=_parse_bool("NAMVIBE_AI_LOG_PROVIDER_USAGE", True),
        cache_ttl_seconds=_parse_int("NAMVIBE_AI_CACHE_TTL_SECONDS", 120, minimum=15, maximum=3600),
        recommendation_version=(os.getenv("NAMVIBE_AI_RECOMMENDATION_VERSION") or "v1").strip() or "v1",
    )
