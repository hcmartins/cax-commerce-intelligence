from typing import Protocol

from app.integrations.base import ProviderCallResult


class SupplierProvider(Protocol):
    """Finds candidate suppliers globally for a given product.

    Concrete providers (Alibaba, Global Sources, a private supplier directory, ...)
    implement this and are looked up by name in `get_supplier_provider()`.
    """

    name: str

    def find_suppliers(
        self,
        product_title: str,
        category: str | None,
        target_unit_price: float,
        currency: str = "USD",
    ) -> ProviderCallResult: ...
