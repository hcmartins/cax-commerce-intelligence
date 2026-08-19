import uuid

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def evaluated_and_unevaluated_opportunities(client):
    run = client.post(
        "/api/v1/runs", json={"query": "wireless earbuds", "filters": {}}
    ).json()
    opportunities = client.get(f"/api/v1/runs/{run['id']}/opportunities").json()
    evaluated = [o for o in opportunities if o["best_offer"]]
    unevaluated = [o for o in opportunities if not o["best_offer"]]
    assert evaluated, "expected at least one evaluated opportunity for this fixture to be useful"
    assert unevaluated, "expected at least one not-yet-evaluated opportunity for this fixture to be useful"
    return evaluated[0], unevaluated[0]


def test_approve_succeeds_for_an_evaluated_opportunity(client, evaluated_and_unevaluated_opportunities):
    evaluated, _unevaluated = evaluated_and_unevaluated_opportunities

    response = client.post(f"/api/v1/opportunities/{evaluated['id']}/approve")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "SENT"
    assert body["external_reference"]
    assert body["error_message"] is None


def test_approve_rejects_an_opportunity_without_profitability_data(
    client, evaluated_and_unevaluated_opportunities
):
    _evaluated, unevaluated = evaluated_and_unevaluated_opportunities

    response = client.post(f"/api/v1/opportunities/{unevaluated['id']}/approve")
    assert response.status_code == 409
    assert "error" in response.json()


def test_approve_404s_for_an_unknown_opportunity(client):
    response = client.post(f"/api/v1/opportunities/{uuid.uuid4()}/approve")
    assert response.status_code == 404


def test_list_approvals_reflects_a_successful_approval(client, evaluated_and_unevaluated_opportunities):
    evaluated, _unevaluated = evaluated_and_unevaluated_opportunities

    client.post(f"/api/v1/opportunities/{evaluated['id']}/approve")

    response = client.get(f"/api/v1/opportunities/{evaluated['id']}/approvals")
    assert response.status_code == 200
    approvals = response.json()
    assert len(approvals) == 1
    assert approvals[0]["status"] == "SENT"


def test_approving_twice_keeps_both_attempts_on_record(client, evaluated_and_unevaluated_opportunities):
    evaluated, _unevaluated = evaluated_and_unevaluated_opportunities

    client.post(f"/api/v1/opportunities/{evaluated['id']}/approve")
    client.post(f"/api/v1/opportunities/{evaluated['id']}/approve")

    approvals = client.get(f"/api/v1/opportunities/{evaluated['id']}/approvals").json()
    assert len(approvals) == 2


def test_approval_survives_a_provider_failure_and_can_be_retried(
    client, evaluated_and_unevaluated_opportunities, monkeypatch
):
    """Regression test for the "fail gracefully and preserve state for retry"
    requirement: the operations service being unreachable must not crash the
    request, must be recorded as FAILED, and a later retry must succeed.
    """

    evaluated, _unevaluated = evaluated_and_unevaluated_opportunities

    import app.modules.operations.service as ops_service

    class _BoomProvider:
        def submit_approval(self, opportunity_id, payload):
            raise ConnectionError("operations service unreachable")

    monkeypatch.setattr(ops_service, "get_operations_provider", lambda: _BoomProvider())

    failed_response = client.post(f"/api/v1/opportunities/{evaluated['id']}/approve")
    assert failed_response.status_code == 201  # the *attempt* was recorded, not a server error
    failed_body = failed_response.json()
    assert failed_body["status"] == "FAILED"
    assert "unreachable" in failed_body["error_message"]

    monkeypatch.undo()

    retry_response = client.post(f"/api/v1/opportunities/{evaluated['id']}/approve")
    assert retry_response.status_code == 201
    assert retry_response.json()["status"] == "SENT"

    approvals = client.get(f"/api/v1/opportunities/{evaluated['id']}/approvals").json()
    assert len(approvals) == 2
    assert {a["status"] for a in approvals} == {"FAILED", "SENT"}
