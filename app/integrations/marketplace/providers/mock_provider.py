import time

from app.config import get_settings
from app.integrations.base import ProviderCallResult

_CATEGORY_FEE_PCT = {
    "Home & Kitchen": 15.0,
    "Fitness": 15.0,
    "Pet Supplies": 15.0,
    "Electronics Accessories": 8.0,
    "Outdoors": 15.0,
}


class MockMarketplaceProvider:
    """Deterministic fake marketplace reference data (fee %, benchmark price)."""

    name = "mock"

    def get_reference_data(
        self, category: str | None, avg_selling_price: float
    ) -> ProviderCallResult:
        start = time.perf_counter()
        settings = get_settings()
        fee_pct = _CATEGORY_FEE_PCT.get(category or "", settings.default_marketplace_fee_pct)
        data = {
            "marketplace_fee_pct": fee_pct,
            "payment_fee_pct": settings.default_payment_fee_pct,
            "reference_selling_price": round(avg_selling_price, 2),
        }
        latency_ms = int((time.perf_counter() - start) * 1000)
        return ProviderCallResult(
            provider_name=self.name,
            request={"category": category, "avg_selling_price": avg_selling_price},
            response=data,
            data=data,
            latency_ms=latency_ms,
        )
