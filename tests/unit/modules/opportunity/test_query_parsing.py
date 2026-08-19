from app.modules.opportunity.query_parsing import (
    SearchCriteria,
    get_or_parse_criteria,
    parse_search_criteria,
)


def test_parses_the_reported_bug_query():
    criteria = parse_search_criteria("Find 10 products suitable for a £200 test budget")
    assert criteria.currency == "GBP"
    assert criteria.budget == 200.0
    assert criteria.number_of_products == 10
    assert criteria.market == "UK"


def test_parses_the_full_demo_scenario_query():
    query = (
        "Find 10 lightweight, non-regulated products suitable for a £200 test budget "
        "in the UK. Prefer products with year-round demand and an estimated margin of "
        "at least 30%."
    )
    criteria = parse_search_criteria(query)
    assert criteria.currency == "GBP"
    assert criteria.budget == 200.0
    assert criteria.number_of_products == 10
    assert criteria.market == "UK"
    assert criteria.min_margin_pct == 30.0


def test_defaults_when_nothing_is_detectable():
    criteria = parse_search_criteria("wireless earbuds")
    assert criteria.currency == "USD"
    assert criteria.budget is None
    assert criteria.number_of_products == 8
    assert criteria.min_margin_pct is None


def test_explicit_filters_take_precedence_over_text_inference():
    criteria = parse_search_criteria(
        "Find 10 products for a £200 budget", filters={"currency": "EUR", "number_of_products": 3}
    )
    assert criteria.currency == "EUR"
    assert criteria.number_of_products == 3


def test_number_of_products_is_capped():
    criteria = parse_search_criteria("Find 500 gadgets")
    assert criteria.number_of_products <= 20


def test_roundtrips_through_dict():
    criteria = parse_search_criteria("Find 10 products suitable for a £200 test budget")
    restored = SearchCriteria.from_dict(criteria.to_dict())
    assert restored == criteria


def test_get_or_parse_criteria_reuses_stored_criteria_instead_of_reparsing():
    stored = SearchCriteria(currency="EUR", number_of_products=99).to_dict()
    # The query text alone would parse to USD/8 — proving this path used the
    # stored dict rather than re-parsing the (here, deliberately mismatched) query.
    criteria = get_or_parse_criteria("wireless earbuds", {"parsed_criteria": stored})
    assert criteria.currency == "EUR"
    assert criteria.number_of_products == 99


def test_get_or_parse_criteria_falls_back_to_parsing_when_nothing_stored():
    criteria = get_or_parse_criteria("Find 10 products for a £200 budget", {})
    assert criteria.currency == "GBP"
