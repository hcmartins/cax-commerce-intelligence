import uuid

from sqlalchemy.orm import Session

from app.integrations.factory import get_ai_provider
from app.shared.call_logger import log_integration_call


class AIClient:
    """Single shared entry point every module uses to talk to the LLM.

    Wraps whichever `AIProvider` is configured (mock, Anthropic, or OpenAI) and guarantees
    every call is logged to `integration_call_log`, so no module needs its own
    AI plumbing or its own logging.
    """

    def complete(
        self,
        db: Session,
        *,
        run_id: uuid.UUID | None,
        module: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 512,
    ) -> str:
        provider = get_ai_provider()
        result = provider.complete(system_prompt, user_prompt, max_tokens=max_tokens)
        log_integration_call(db, run_id=run_id, module=module, provider_category="ai", result=result)
        return result.data or ""


def get_ai_client() -> AIClient:
    return AIClient()
