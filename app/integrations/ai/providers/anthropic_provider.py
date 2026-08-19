import time

from app.integrations.base import ProviderCallResult


class AnthropicAIProvider:
    """Thin adapter over the Anthropic SDK, conforming to `AIProvider`."""

    name = "anthropic"

    def __init__(self, api_key: str, model: str) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(
        self, system_prompt: str, user_prompt: str, max_tokens: int = 512
    ) -> ProviderCallResult:
        start = time.perf_counter()
        try:
            message = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = "".join(block.text for block in message.content if hasattr(block, "text"))
            latency_ms = int((time.perf_counter() - start) * 1000)
            usage = getattr(message, "usage", None)
            tokens_used = (
                (usage.input_tokens + usage.output_tokens) if usage is not None else None
            )
            return ProviderCallResult(
                provider_name=self.name,
                request={"model": self._model, "system_prompt": system_prompt, "user_prompt": user_prompt},
                response={"text": text},
                data=text,
                latency_ms=latency_ms,
                tokens_used=tokens_used,
                status="success",
            )
        except Exception as exc:  # noqa: BLE001 - surfaced via ProviderCallResult, not raised
            latency_ms = int((time.perf_counter() - start) * 1000)
            return ProviderCallResult(
                provider_name=self.name,
                request={"model": self._model, "system_prompt": system_prompt, "user_prompt": user_prompt},
                response={},
                data=None,
                latency_ms=latency_ms,
                status="error",
                error_message=str(exc),
            )
