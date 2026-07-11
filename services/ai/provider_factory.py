from services.ai.config import get_ai_config
from services.ai.provider_disabled import DisabledAIProvider


def get_ai_provider():
    config = get_ai_config()
    if not config.external_calls_enabled:
        return DisabledAIProvider(reason="external_calls_disabled")
    if config.provider in {"", "disabled"}:
        return DisabledAIProvider(reason="provider_not_configured")
    return DisabledAIProvider(reason="provider_not_implemented")
