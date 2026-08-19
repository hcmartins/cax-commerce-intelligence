from app.integrations.search.providers.mock_provider import MockSearchProvider
from app.modules.opportunity.validation import find_duplicate_indices, is_valid_product_title

QUERY = "Find 10 products suitable for a £200 test budget"


def test_generated_titles_never_leak_the_query():
    """Regression test for the reported bug: titles like "Compact Find 10 Products
    Suitable For A £200 Test Budget Pro" leaking the raw search request.
    """

    provider = MockSearchProvider()
    result = provider.search_products(QUERY, {"number_of_products": 10, "currency": "GBP"})

    assert len(result.data) == 10
    for candidate in result.data:
        valid, reason = is_valid_product_title(candidate["title"], QUERY)
        assert valid, f"{candidate['title']!r} failed validation: {reason}"


def test_respects_requested_count():
    provider = MockSearchProvider()
    result = provider.search_products("wireless earbuds", {"number_of_products": 5})
    assert len(result.data) == 5


def test_respects_requested_currency():
    provider = MockSearchProvider()
    result = provider.search_products("wireless earbuds", {"currency": "GBP"})
    assert all(c["currency"] == "GBP" for c in result.data)


def test_defaults_to_usd_without_a_currency_filter():
    provider = MockSearchProvider()
    result = provider.search_products("wireless earbuds", {})
    assert all(c["currency"] == "USD" for c in result.data)


def test_generated_candidates_have_no_duplicate_titles():
    provider = MockSearchProvider()
    result = provider.search_products(QUERY, {"number_of_products": 15})
    titles = [c["title"] for c in result.data]
    assert find_duplicate_indices(titles) == set()


def test_same_query_produces_the_same_results_deterministically():
    provider = MockSearchProvider()
    first = provider.search_products(QUERY, {"number_of_products": 10, "currency": "GBP"})
    second = provider.search_products(QUERY, {"number_of_products": 10, "currency": "GBP"})
    assert [c["title"] for c in first.data] == [c["title"] for c in second.data]
