import pytest

from app.modules.opportunity.validation import find_duplicate_indices, is_valid_product_title

QUERY = "Find 10 products suitable for a £200 test budget"


@pytest.mark.parametrize(
    "title",
    [
        "Compact Find 10 Products Suitable For A £200 Test Budget Pro",
        "Portable Find 10 Products Suitable For A £200 Test Budget Kit",
        "Premium Find 10 Products Suitable For A £200 Test Budget",
    ],
)
def test_rejects_the_reported_bug_titles(title):
    """Regression test for the exact titles reported: the search request leaking
    verbatim into the generated product name.
    """

    valid, reason = is_valid_product_title(title, QUERY)
    assert not valid
    assert reason


@pytest.mark.parametrize(
    "title",
    [
        "Adjustable Drawer Organiser Set",
        "Car Seat Gap Organiser",
        "Reusable Silicone Food Storage Set",
        "Cable Management Box",
        "Pet Hair Remover Roller",
    ],
)
def test_accepts_genuine_product_names(title):
    valid, reason = is_valid_product_title(title, QUERY)
    assert valid, reason


def test_rejects_titles_containing_the_budget_instruction():
    valid, _ = is_valid_product_title("Premium £200 Test Budget Organiser", QUERY)
    assert not valid


def test_rejects_excessively_long_titles():
    valid, reason = is_valid_product_title("A " * 60, QUERY)
    assert not valid
    assert "long" in reason


def test_rejects_excessively_short_titles():
    valid, reason = is_valid_product_title("Ab", QUERY)
    assert not valid
    assert "short" in reason


def test_find_duplicate_indices_flags_repeats_but_not_distinct_titles():
    titles = [
        "Adjustable Drawer Organiser Set",
        "adjustable drawer organiser set",  # same product, different case
        "Cable Management Box",
        "Premium Adjustable Drawer Organiser Set",  # near-duplicate (one adjective)
        "Pet Hair Remover Roller",
    ]
    duplicates = find_duplicate_indices(titles)
    assert duplicates == {1, 3}


def test_find_duplicate_indices_handles_an_empty_list():
    assert find_duplicate_indices([]) == set()
