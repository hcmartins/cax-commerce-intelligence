import pytest

import app.modules.runs.service as runs_service
from app.modules.opportunity import repository as opportunity_repository
from app.modules.profitability import repository as profitability_repository
from app.modules.runs.models import RunStatus
from app.modules.runs.service import run_search
from app.modules.suppliers import repository as suppliers_repository
from app.shared.models import IntegrationCallLog

pytestmark = pytest.mark.integration


def test_run_search_completes_and_persists_the_full_pipeline(db_session):
    run = run_search(db_session, query="wireless earbuds", filters={"max_price": 50})

    assert run.status == RunStatus.COMPLETE
    assert run.completed_at is not None
    assert run.error_message is None

    opportunities = opportunity_repository.list_by_run(db_session, run.id)
    assert len(opportunities) > 0
    assert all(o.run_id == run.id for o in opportunities)
    assert opportunities[0].rank == 1

    evaluated = opportunities[: runs_service.MAX_OPPORTUNITIES_TO_EVALUATE]
    top = evaluated[0]

    offers = suppliers_repository.list_by_opportunity(db_session, top.id)
    assert len(offers) > 0
    assert all(o.supplier_id is not None for o in offers)
    assert all(o.product_opportunity_id == top.id for o in offers)

    calcs = profitability_repository.list_by_opportunity(db_session, top.id)
    assert len(calcs) == len(offers)
    assert all(c.recommendation is not None for c in calcs)
    assert all(c.recommendation.decision in ("BUY_TEST", "WATCH", "REJECT") for c in calcs)

    logs = db_session.query(IntegrationCallLog).filter(IntegrationCallLog.run_id == run.id).all()
    # one search-provider call, plus one supplier-provider call per evaluated opportunity
    assert len(logs) == 1 + len(evaluated)


def test_run_search_twice_reuses_deduplicated_suppliers(db_session):
    """Regression test: the mock provider can generate the same company name for two
    different opportunities. A second identical search must reuse that supplier
    rather than raise on a lookup that now matches more than one row.
    """

    run_search(db_session, query="wireless earbuds", filters={})
    second = run_search(db_session, query="wireless earbuds", filters={})

    assert second.status == RunStatus.COMPLETE


def test_run_search_marks_failed_and_rolls_back_on_a_mid_pipeline_error(db_session, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("simulated provider outage")

    monkeypatch.setattr(runs_service, "discover_opportunities", _boom)

    run = run_search(db_session, query="will fail", filters={})

    assert run.status == RunStatus.FAILED
    assert run.error_message is not None
    assert "simulated provider outage" in run.error_message
    assert opportunity_repository.list_by_run(db_session, run.id) == []
