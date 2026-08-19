"""Thin HTTP client the dashboard uses to talk to the API — its only coupling point
to the backend. Same rule as any other API client: no direct database or module
access, so the UI could be swapped out entirely without touching the backend.
"""

import os
from typing import Any

import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")
DEFAULT_TIMEOUT = 30


class ApiError(Exception):
    """Raised for any non-2xx response, carrying what the API's error envelope said."""

    def __init__(self, status_code: int, message: str, details: Any = None) -> None:
        self.status_code = status_code
        self.message = message
        self.details = details
        super().__init__(f"{status_code}: {message}")


def _request(method: str, path: str, **kwargs: Any) -> Any:
    url = f"{API_BASE_URL}{path}"
    try:
        response = requests.request(method, url, timeout=DEFAULT_TIMEOUT, **kwargs)
    except requests.exceptions.RequestException as exc:
        raise ApiError(0, f"Could not reach the API at {API_BASE_URL}: {exc}") from exc

    if not response.ok:
        try:
            error = response.json().get("error", {})
        except ValueError:
            error = {}
        raise ApiError(
            response.status_code,
            error.get("message", response.text or "Unknown error"),
            error.get("details"),
        )

    if response.status_code == 204 or not response.content:
        return None
    return response.json()


def health_check() -> dict:
    return _request("GET", "/health")


def start_run(query: str, filters: dict | None = None) -> dict:
    return _request("POST", "/runs", json={"query": query, "filters": filters or {}})


def list_runs(limit: int = 50, offset: int = 0) -> list[dict]:
    return _request("GET", "/runs", params={"limit": limit, "offset": offset})


def get_run(run_id: str) -> dict:
    return _request("GET", f"/runs/{run_id}")


def list_run_opportunities(run_id: str) -> list[dict]:
    return _request("GET", f"/runs/{run_id}/opportunities")


def get_opportunity(opportunity_id: str) -> dict:
    return _request("GET", f"/opportunities/{opportunity_id}")


def list_opportunity_suppliers(opportunity_id: str) -> list[dict]:
    return _request("GET", f"/opportunities/{opportunity_id}/suppliers")


def list_opportunity_profitability(opportunity_id: str) -> list[dict]:
    return _request("GET", f"/opportunities/{opportunity_id}/profitability")


def recalculate_profitability(
    opportunity_id: str,
    *,
    supplier_offer_id: str,
    selling_price: float | None = None,
    marketplace_fee_pct: float | None = None,
    payment_fee_pct: float | None = None,
    other_costs: float = 0.0,
) -> dict:
    payload = {
        "supplier_offer_id": supplier_offer_id,
        "selling_price": selling_price,
        "marketplace_fee_pct": marketplace_fee_pct,
        "payment_fee_pct": payment_fee_pct,
        "other_costs": other_costs,
    }
    return _request(
        "POST", f"/opportunities/{opportunity_id}/profitability:recalculate", json=payload
    )


def approve_opportunity(opportunity_id: str) -> dict:
    return _request("POST", f"/opportunities/{opportunity_id}/approve")


def list_opportunity_approvals(opportunity_id: str) -> list[dict]:
    return _request("GET", f"/opportunities/{opportunity_id}/approvals")
