from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderCallResult:
    """Envelope every integration provider returns, so callers can log it uniformly."""

    provider_name: str
    request: dict[str, Any]
    response: dict[str, Any]
    data: Any
    latency_ms: int
    tokens_used: int | None = None
    cost_usd: float | None = None
    status: str = "success"
    error_message: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
