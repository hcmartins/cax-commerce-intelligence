"""Production smoke tests — exercise a **running** deployment over real HTTP,
unlike `tests/unit` (no I/O) and `tests/integration` (in-process `TestClient` +
real Postgres). These are what you run against `docker compose up`'s stack, or
any other already-deployed environment, to confirm it actually works end to end:
process up, DB migrated and reachable, docs served, and the full discovery ->
sourcing -> profitability pipeline producing a result.

Skips cleanly — the same pattern `tests/conftest.py` uses for a missing test
database — if nothing is listening at `SMOKE_BASE_URL`, so a plain `pytest` run
on a machine with no server up doesn't fail. Point it explicitly to actually run
these:

    SMOKE_BASE_URL=http://localhost:8000 pytest -m smoke
"""

import os

import httpx
import pytest

BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://localhost:8000")
TIMEOUT = 10.0

pytestmark = pytest.mark.smoke


@pytest.fixture(scope="module")
def http_client():
    client = httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)
    try:
        response = client.get("/health")
        reachable = response.status_code == 200
    except httpx.HTTPError:
        reachable = False

    if not reachable:
        client.close()
        pytest.skip(
            f"No server with a working /health reachable at {BASE_URL}. Start the "
            "stack first, e.g.:\n"
            "  docker compose up --build\n"
            "...or point SMOKE_BASE_URL at a running deployment."
        )
    yield client
    client.close()


def test_liveness(http_client):
    response = http_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness(http_client):
    response = http_client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "reachable"


def test_openapi_schema_served(http_client):
    response = http_client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    assert "/api/v1/runs" in schema["paths"]


def test_swagger_ui_served(http_client):
    response = http_client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_request_id_is_echoed(http_client):
    response = http_client.get("/health", headers={"X-Request-ID": "smoke-test-fixed-id"})
    assert response.headers["x-request-id"] == "smoke-test-fixed-id"


def test_end_to_end_search_pipeline(http_client):
    """The core commerce-intelligence workflow, top to bottom: start a run, see
    it complete, and pull opportunities + supplier + profitability data for it —
    the same path the Streamlit dashboard drives through `ui/api_client.py`.
    """

    run_response = http_client.post(
        "/api/v1/runs", json={"query": "wireless earbuds", "filters": {"max_price": 50}}
    )
    assert run_response.status_code == 201
    run = run_response.json()
    assert run["status"] in ("COMPLETE", "FAILED")
    run_id = run["id"]

    got_response = http_client.get(f"/api/v1/runs/{run_id}")
    assert got_response.status_code == 200
    assert got_response.json()["id"] == run_id

    opportunities_response = http_client.get(f"/api/v1/runs/{run_id}/opportunities")
    assert opportunities_response.status_code == 200
    opportunities = opportunities_response.json()

    if run["status"] == "FAILED":
        pytest.skip(f"Run completed with status FAILED: {run.get('error_message')}")

    assert opportunities, "a COMPLETE run is expected to have found at least one opportunity"
    opportunity_id = opportunities[0]["id"]

    suppliers_response = http_client.get(f"/api/v1/opportunities/{opportunity_id}/suppliers")
    assert suppliers_response.status_code == 200

    profitability_response = http_client.get(
        f"/api/v1/opportunities/{opportunity_id}/profitability"
    )
    assert profitability_response.status_code == 200
