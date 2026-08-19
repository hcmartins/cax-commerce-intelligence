import time

from app.integrations.base import ProviderCallResult


class OpenAIAIProvider:
    """Thin adapter over the OpenAI SDK, conforming to `AIProvider`."""

    name = "openai"

    def __init__(self, api_key: str, model: str) -> None:
        import openai

        self._client = openai.OpenAI(api_key=api_key)
        self._model = model

    def complete(
        self, system_prompt: str, user_prompt: str, max_tokens: int = 512
    ) -> ProviderCallResult:
        start = time.perf_counter()
        request = {"model": self._model, "system_prompt": system_prompt, "user_prompt": user_prompt}
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                max_completion_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            text = response.choices[0].message.content or ""
            latency_ms = int((time.perf_counter() - start) * 1000)
            usage = getattr(response, "usage", None)
            tokens_used = usage.total_tokens if usage is not None else None
            return ProviderCallResult(
                provider_name=self.name,
                request=request,
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
                request=request,
                response={},
                data=None,
                latency_ms=latency_ms,
                status="error",
                error_message=str(exc),
            )
