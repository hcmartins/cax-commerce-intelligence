from typing import Protocol

from app.integrations.base import ProviderCallResult


class MarketplaceProvider(Protocol):
    """Supplies marketplace reference data: fee schedules and price benchmarks.

    Used by the profitability module to fill in sensible defaults (fee %, reference
    selling price) when the caller doesn't supply their own assumptions.
    """

    name: str

    def get_reference_data(
        self, category: str | None, avg_selling_price: float
    ) -> ProviderCallResult: ...
