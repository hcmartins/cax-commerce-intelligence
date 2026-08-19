import pytest

from app.modules.opportunity.models import ProductOpportunity
from app.modules.opportunity.ranking import compute_overall_score, rank_opportunities


@pytest.mark.parametrize(
    "demand, competition, trend, expected",
    [
        (100, 0, 100, 100.0),  # best possible: full demand/trend, zero competition
        (0, 100, 0, 0.0),  # worst possible: no demand/trend, full competition
        (50, 50, 50, 50.0),  # a perfectly average candidate scores exactly average
        (80, 20, 60, 74.0),  # 80*0.4 + 60*0.3 + (100-20)*0.3 = 32 + 18 + 24
    ],
)
def test_compute_overall_score(demand, competition, trend, expected):
    assert compute_overall_score(demand, competition, trend) == expected


def test_compute_overall_score_clamps_to_0_100():
    assert compute_overall_score(demand_score=1000, competition_score=0, trend_score=1000) == 100.0
    assert compute_overall_score(demand_score=-1000, competition_score=1000, trend_score=-1000) == 0.0


def test_rank_opportunities_orders_best_first_and_assigns_rank():
    high = ProductOpportunity(
        title="high", source="mock", demand_score=90, competition_score=10, trend_score=90
    )
    mid = ProductOpportunity(
        title="mid", source="mock", demand_score=50, competition_score=50, trend_score=50
    )
    low = ProductOpportunity(
        title="low", source="mock", demand_score=10, competition_score=90, trend_score=10
    )

    ranked = rank_opportunities([mid, low, high])

    assert [o.title for o in ranked] == ["high", "mid", "low"]
    assert [o.rank for o in ranked] == [1, 2, 3]
    assert ranked[0].overall_score > ranked[1].overall_score > ranked[2].overall_score


def test_rank_opportunities_handles_an_empty_list():
    assert rank_opportunities([]) == []


def test_ranking_is_deterministic_for_identical_inputs():
    def build():
        return [
            ProductOpportunity(
                title="a", source="mock", demand_score=90, competition_score=10, trend_score=90
            ),
            ProductOpportunity(
                title="b", source="mock", demand_score=50, competition_score=50, trend_score=50
            ),
            ProductOpportunity(
                title="c", source="mock", demand_score=10, competition_score=90, trend_score=10
            ),
        ]

    first = rank_opportunities(build())
    second = rank_opportunities(build())

    assert [o.title for o in first] == [o.title for o in second]
    assert [o.overall_score for o in first] == [o.overall_score for o in second]
    assert [o.rank for o in first] == [o.rank for o in second]
