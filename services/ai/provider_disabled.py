from services.ai.provider_base import AIProvider, AIProviderUnavailable


class DisabledAIProvider(AIProvider):
    def __init__(self, reason="external_ai_disabled"):
        self.reason = reason or "external_ai_disabled"

    def generate_text(self, prompt, *, metadata=None, request_id=None, max_output_tokens=None):
        raise AIProviderUnavailable(f"AI provider unavailable: {self.reason}")

    def healthcheck(self):
        return {
            "available": False,
            "provider": "disabled",
            "reason": self.reason,
        }
