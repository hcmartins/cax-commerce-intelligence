import uuid

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def opportunity_with_offer(client):
    run = client.post("/api/v1/runs", json={"query": "wireless earbuds", "filters": {}}).json()
    opportunities = client.get(f"/api/v1/runs/{run['id']}/opportunities").json()
    opp_id = opportunities[0]["id"]
    offers = client.get(f"/api/v1/opportunities/{opp_id}/suppliers").json()
    return opp_id, offers[0]["id"]


def test_get_opportunity_suppliers_404_for_unknown_opportunity(client):
    response = client.get(f"/api/v1/opportunities/{uuid.uuid4()}/suppliers")
    assert response.status_code == 404


def test_get_opportunity_profitability_404_for_unknown_opportunity(client):
    response = client.get(f"/api/v1/opportunities/{uuid.uuid4()}/profitability")
    assert response.status_code == 404


def test_recalculate_with_overrides_returns_a_new_calculation(client, opportunity_with_offer):
    opp_id, offer_id = opportunity_with_offer

    response = client.post(
        f"/api/v1/opportunities/{opp_id}/profitability:recalculate",
        json={"supplier_offer_id": offer_id, "selling_price": 200.0, "marketplace_fee_pct": 10.0},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["selling_price"] == 200.0
    assert body["assumptions"]["marketplace_fee_pct"] == 10.0
    assert body["assumptions"]["selling_price_source"] == "override"
    assert body["recommendation"]["decision"] in ("BUY_TEST", "WATCH", "REJECT")


def test_recalculate_leaves_the_original_calculation_in_place(client, opportunity_with_offer):
    opp_id, offer_id = opportunity_with_offer

    before = client.get(f"/api/v1/opportunities/{opp_id}/profitability").json()

    client.post(
        f"/api/v1/opportunities/{opp_id}/profitability:recalculate",
        json={"supplier_offer_id": offer_id, "selling_price": 200.0},
    )

    after = client.get(f"/api/v1/opportunities/{opp_id}/profitability").json()
    assert len(after) == len(before) + 1


def test_recalculate_rejects_an_offer_from_a_different_opportunity(client, opportunity_with_offer):
    _opp_id, offer_id = opportunity_with_offer

    other_run = client.post("/api/v1/runs", json={"query": "phone case", "filters": {}}).json()
    other_opportunities = client.get(f"/api/v1/runs/{other_run['id']}/opportunities").json()
    other_opp_id = other_opportunities[0]["id"]

    response = client.post(
        f"/api/v1/opportunities/{other_opp_id}/profitability:recalculate",
        json={"supplier_offer_id": offer_id},
    )
    assert response.status_code == 404


def test_recalculate_rejects_a_negative_selling_price(client, opportunity_with_offer):
    opp_id, offer_id = opportunity_with_offer

    response = client.post(
        f"/api/v1/opportunities/{opp_id}/profitability:recalculate",
        json={"supplier_offer_id": offer_id, "selling_price": -5},
    )
    assert response.status_code == 422
