"""`ui/` deliberately imports nothing from `app/` (it's a separate HTTP client of
the API), so its modules aren't on the normal package path — this adds `ui/` to
`sys.path` the same way `streamlit run ui/app.py` does at runtime, so its pure
(non-widget) functions can be unit-tested directly.
"""

import sys
from pathlib import Path

UI_DIR = Path(__file__).resolve().parents[3] / "ui"
if str(UI_DIR) not in sys.path:
    sys.path.insert(0, str(UI_DIR))

from components import (  # noqa: E402
    build_why_recommended,
    format_currency,
    format_pct,
    interpret_competition,
    interpret_demand,
)


def test_format_currency_uses_real_symbols_not_currency_codes():
    assert format_currency(5.5, "GBP") == "£5.50"
    assert format_currency(12.99, "EUR") == "€12.99"
    assert format_currency(24.95, "USD") == "$24.95"


def test_format_currency_never_truncates():
    # the reported bug was a *display* truncation ("$5..."), not a value that was
    # actually short — this pins the formatter to always produce the full number.
    assert format_currency(1234567.89, "GBP") == "£1,234,567.89"


def test_format_currency_handles_missing_value():
    assert format_currency(None, "GBP") == "—"


def test_format_pct_handles_missing_value():
    assert format_pct(None) == "—"


def test_high_demand_is_favourable():
    label, tone = interpret_demand(90)
    assert label == "High"
    assert tone == "good"


def test_low_demand_is_unfavourable():
    label, tone = interpret_demand(10)
    assert label == "Low"
    assert tone == "bad"


def test_high_competition_is_unfavourable():
    """The inverse of demand: a high score here is bad news, not good, so it must
    not get the same "good" tone a high demand score gets.
    """

    label, tone = interpret_competition(90)
    assert label == "High"
    assert tone == "bad"


def test_low_competition_is_favourable():
    label, tone = interpret_competition(10)
    assert label == "Low"
    assert tone == "good"


def test_why_recommended_mentions_evaluated_margin_when_available():
    opportunity = {
        "demand_score": 84,
        "competition_score": 46,
        "best_offer": {"margin_pct": 40.0, "roi_pct": 120.0},
    }
    text = build_why_recommended(opportunity)
    assert "40%" in text
    assert "120%" in text


def test_why_recommended_explains_missing_data_without_fabricating_numbers():
    opportunity = {"demand_score": 84, "competition_score": 46, "best_offer": None}
    text = build_why_recommended(opportunity)
    assert "%" not in text  # no margin/ROI figure exists yet — must not invent one
