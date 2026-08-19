import time
import uuid
from typing import Any

from app.integrations.base import ProviderCallResult


class MockOperationsProvider:
    """Stands in for the real Commerce Operations platform, which lives in a
    separate repository this codebase doesn't have access to. Simulates a
    successful hand-off (an accepted, queued approval) with zero external
    dependencies — swap in a real HTTP client behind the same interface once
    that service exists and is reachable.
    """

    name = "mock"

    def submit_approval(self, opportunity_id: str, payload: dict[str, Any]) -> ProviderCallResult:
        start = time.perf_counter()
        external_reference = f"mock-ops-{uuid.uuid4().hex[:12]}"
        latency_ms = int((time.perf_counter() - start) * 1000)
        return ProviderCallResult(
            provider_name=self.name,
            request={"opportunity_id": opportunity_id, "payload": payload},
            response={"external_reference": external_reference, "status": "queued"},
            data={"external_reference": external_reference},
            latency_ms=latency_ms,
        )
