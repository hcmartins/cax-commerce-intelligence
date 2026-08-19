import pytest

from app.config import get_settings
from app.integrations import factory
from app.integrations.ai.providers.anthropic_provider import AnthropicAIProvider
from app.integrations.ai.providers.mock_provider import MockAIProvider
from app.integrations.ai.providers.openai_provider import OpenAIAIProvider
from app.integrations.marketplace.providers.mock_provider import MockMarketplaceProvider
from app.integrations.search.providers.mock_provider import MockSearchProvider
from app.integrations.suppliers.providers.mock_provider import MockSupplierProvider


@pytest.fixture(autouse=True)
def _clear_caches():
    """Every factory getter (and get_settings) is @lru_cache'd for the app's actual
    runtime, which would otherwise leak a cached provider — or a cached Settings
    object built from a previous test's monkeypatched env vars — into the next test.
    """

    def _clear_all():
        get_settings.cache_clear()
        factory.get_search_provider.cache_clear()
        factory.get_supplier_provider.cache_clear()
        factory.get_marketplace_provider.cache_clear()
        factory.get_ai_provider.cache_clear()

    _clear_all()
    yield
    _clear_all()


def test_default_settings_select_every_mock_provider(monkeypatch):
    # Pinned explicitly rather than relying on ambient defaults: a developer's own
    # .env (this repo's included) may set AI_PROVIDER=auto with a real key, which
    # is correct for running the app but would make "default" here mean whatever
    # that file happens to contain instead of the library default this asserts.
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    assert isinstance(factory.get_search_provider(), MockSearchProvider)
    assert isinstance(factory.get_supplier_provider(), MockSupplierProvider)
    assert isinstance(factory.get_marketplace_provider(), MockMarketplaceProvider)
    assert isinstance(factory.get_ai_provider(), MockAIProvider)


def test_ai_provider_falls_back_to_mock_without_an_api_key(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    assert isinstance(factory.get_ai_provider(), MockAIProvider)


def test_ai_provider_uses_anthropic_when_configured_with_a_key(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    assert isinstance(factory.get_ai_provider(), AnthropicAIProvider)


def test_ai_provider_falls_back_to_mock_when_openai_forced_without_a_key(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    assert isinstance(factory.get_ai_provider(), MockAIProvider)


def test_ai_provider_uses_openai_when_configured_with_a_key(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    assert isinstance(factory.get_ai_provider(), OpenAIAIProvider)


def test_auto_prefers_anthropic_when_both_keys_are_set(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "auto")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    assert isinstance(factory.get_ai_provider(), AnthropicAIProvider)


def test_auto_falls_back_to_openai_when_anthropic_key_is_missing(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "auto")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    assert isinstance(factory.get_ai_provider(), OpenAIAIProvider)


def test_auto_falls_back_to_mock_when_neither_key_is_set(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "auto")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    assert isinstance(factory.get_ai_provider(), MockAIProvider)
