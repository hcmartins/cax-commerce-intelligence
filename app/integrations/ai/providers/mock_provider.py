import time

from app.integrations.base import ProviderCallResult


class MockAIProvider:
    """Deterministic fake AI provider so the pipeline runs with zero API keys.

    Returns a short templated rationale instead of calling a real model. Swap
    `AI_PROVIDER=anthropic` (with `ANTHROPIC_API_KEY` set) to use a real model
    without changing any calling code.
    """

    name = "mock"

    def complete(
        self, system_prompt: str, user_prompt: str, max_tokens: int = 512
    ) -> ProviderCallResult:
        start = time.perf_counter()
        text = (
            "Mock AI rationale: based on the supplied demand, competition and margin "
            "signals, this opportunity was evaluated using rule-based heuristics "
            "(no live model call was made)."
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        return ProviderCallResult(
            provider_name=self.name,
            request={"system_prompt": system_prompt, "user_prompt": user_prompt},
            response={"text": text},
            data=text,
            latency_ms=latency_ms,
            tokens_used=0,
            cost_usd=0.0,
        )
