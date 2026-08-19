import uuid

import pytest

pytestmark = pytest.mark.integration


def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_full_run_lifecycle_via_the_api(client):
    start = client.post(
        "/api/v1/runs", json={"query": "wireless earbuds", "filters": {"max_price": 50}}
    )
    assert start.status_code == 201, start.text
    run = start.json()
    assert run["status"] == "COMPLETE"

    listing = client.get("/api/v1/runs")
    assert listing.status_code == 200
    assert any(r["id"] == run["id"] for r in listing.json())

    detail = client.get(f"/api/v1/runs/{run['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == run["id"]

    opportunities = client.get(f"/api/v1/runs/{run['id']}/opportunities")
    assert opportunities.status_code == 200
    opp_list = opportunities.json()
    assert len(opp_list) > 0
    assert opp_list[0]["rank"] == 1
    opp_id = opp_list[0]["id"]

    opp_detail = client.get(f"/api/v1/opportunities/{opp_id}")
    assert opp_detail.status_code == 200
    assert "raw_evidence" in opp_detail.json()

    suppliers = client.get(f"/api/v1/opportunities/{opp_id}/suppliers")
    assert suppliers.status_code == 200
    offers = suppliers.json()
    assert len(offers) > 0
    assert "name" in offers[0]["supplier"]

    profitability = client.get(f"/api/v1/opportunities/{opp_id}/profitability")
    assert profitability.status_code == 200
    calcs = profitability.json()
    assert len(calcs) == len(offers)
    assert calcs[0]["recommendation"]["decision"] in ("BUY_TEST", "WATCH", "REJECT")


def test_get_run_404_for_unknown_id(client):
    response = client.get(f"/api/v1/runs/{uuid.uuid4()}")
    assert response.status_code == 404
    assert "error" in response.json()


def test_get_run_opportunities_404_for_unknown_run(client):
    response = client.get(f"/api/v1/runs/{uuid.uuid4()}/opportunities")
    assert response.status_code == 404


def test_start_run_rejects_an_empty_query(client):
    response = client.post("/api/v1/runs", json={"query": ""})
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "Validation failed"


def test_list_runs_rejects_invalid_pagination(client):
    response = client.get("/api/v1/runs?limit=0")
    assert response.status_code == 422
