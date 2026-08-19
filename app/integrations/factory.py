from functools import lru_cache

from app.config import get_settings
from app.integrations.ai.interface import AIProvider
from app.integrations.marketplace.interface import MarketplaceProvider
from app.integrations.operations.interface import OperationsProvider
from app.integrations.search.interface import SearchProvider
from app.integrations.suppliers.interface import SupplierProvider


@lru_cache
def get_search_provider() -> SearchProvider:
    from app.integrations.search.providers.mock_provider import MockSearchProvider

    settings = get_settings()
    if settings.search_provider == "mock":
        return MockSearchProvider()
    raise ValueError(f"Unknown search provider: {settings.search_provider}")


@lru_cache
def get_marketplace_provider() -> MarketplaceProvider:
    from app.integrations.marketplace.providers.mock_provider import MockMarketplaceProvider

    settings = get_settings()
    if settings.marketplace_provider == "mock":
        return MockMarketplaceProvider()
    raise ValueError(f"Unknown marketplace provider: {settings.marketplace_provider}")


@lru_cache
def get_supplier_provider() -> SupplierProvider:
    from app.integrations.suppliers.providers.mock_provider import MockSupplierProvider

    settings = get_settings()
    if settings.supplier_provider == "mock":
        return MockSupplierProvider()
    raise ValueError(f"Unknown supplier provider: {settings.supplier_provider}")


@lru_cache
def get_operations_provider() -> OperationsProvider:
    from app.integrations.operations.providers.mock_provider import MockOperationsProvider

    settings = get_settings()
    if settings.operations_provider == "mock":
        return MockOperationsProvider()
    raise ValueError(f"Unknown operations provider: {settings.operations_provider}")


@lru_cache
def get_ai_provider() -> AIProvider:
    from app.integrations.ai.providers.mock_provider import MockAIProvider

    settings = get_settings()

    # "auto" tries Anthropic first, then OpenAI, using whichever key is actually
    # set; "anthropic"/"openai" force that specific provider (still falling back to
    # mock if its key is missing, same as the original anthropic-only behavior).
    use_anthropic = settings.anthropic_api_key and settings.ai_provider in ("anthropic", "auto")
    use_openai = settings.openai_api_key and settings.ai_provider in ("openai", "auto")

    if use_anthropic:
        from app.integrations.ai.providers.anthropic_provider import AnthropicAIProvider

        return AnthropicAIProvider(
            api_key=settings.anthropic_api_key, model=settings.anthropic_model
        )
    if use_openai:
        from app.integrations.ai.providers.openai_provider import OpenAIAIProvider

        return OpenAIAIProvider(api_key=settings.openai_api_key, model=settings.openai_model)

    return MockAIProvider()
