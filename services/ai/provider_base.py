from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class AIProviderError(Exception):
    pass


class AIProviderUnavailable(AIProviderError):
    pass


@dataclass(frozen=True)
class AIProviderResponse:
    text: str
    provider: str
    model: str
    input_units: int
    output_units: int
    latency_ms: int
    request_id: str
    raw_metadata: dict = field(default_factory=dict)


class AIProvider(ABC):
    @abstractmethod
    def generate_text(self, prompt, *, metadata=None, request_id=None, max_output_tokens=None):
        raise NotImplementedError

    @abstractmethod
    def healthcheck(self):
        raise NotImplementedError
