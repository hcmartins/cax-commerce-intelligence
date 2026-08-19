from typing import Any, Protocol

from app.integrations.base import ProviderCallResult


class SearchProvider(Protocol):
    """Finds candidate product ideas for a free-text query.

    Concrete providers (SerpApi, Google Trends, a marketplace's own search API, ...)
    implement this and are looked up by name in `get_search_provider()`.
    """

    name: str

    def search_products(
        self, query: str, filters: dict[str, Any] | None = None
    ) -> ProviderCallResult: ...
