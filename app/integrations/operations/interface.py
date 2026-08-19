from typing import Any, Protocol

from app.integrations.base import ProviderCallResult


class OperationsProvider(Protocol):
    """Hands an approved opportunity to the separate Commerce Operations platform
    (procurement -> inventory -> listing -> orders -> customer ops) — this repo
    stops at "approved for operations" and never implements that side itself.

    Concrete providers (an HTTP client for the real Operations service, ...)
    implement this and are looked up by name in `get_operations_provider()`.
    """

    name: str

    def submit_approval(self, opportunity_id: str, payload: dict[str, Any]) -> ProviderCallResult: ...
