from typing import Protocol

from app.integrations.base import ProviderCallResult


class AIProvider(Protocol):
    """A single shared LLM interface used by every module (ranking rationale,
    supplier-summary enrichment, decision explanations, ...).

    Modules never talk to an SDK directly — they go through this interface, via
    `app.shared.ai.client.get_ai_client()`, so there is exactly one place that knows
    how to call the underlying model and exactly one place that logs the call.
    """

    name: str

    def complete(
        self, system_prompt: str, user_prompt: str, max_tokens: int = 512
    ) -> ProviderCallResult: ...
