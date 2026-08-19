"""Turns a free-text search request into structured `SearchCriteria`.

Deliberately rule-based (regex/keyword matching), not an LLM call — this is parsing
*intent* out of a short, fairly formulaic sentence ("find N products for a £X
budget..."), which doesn't need a model, and keeping it deterministic means the
same query always parses the same way. See `opportunity/ranking.py` and
`profitability/calculator.py` for the same "pure function, no I/O" pattern.

The critical property this exists to guarantee: parsed criteria are stored
separately from generated product data and are never substituted into a product
title (see `validation.py` for the enforcement side of that).
"""

import re
from dataclasses import asdict, dataclass, field

DEFAULT_NUMBER_OF_PRODUCTS = 8
MAX_NUMBER_OF_PRODUCTS = 20

_CURRENCY_SYMBOLS = {"£": "GBP", "€": "EUR", "$": "USD"}
_CURRENCY_WORDS = {
    "gbp": "GBP",
    "pounds": "GBP",
    "pound": "GBP",
    "sterling": "GBP",
    "eur": "EUR",
    "euros": "EUR",
    "euro": "EUR",
    "usd": "USD",
    "dollars": "USD",
    "dollar": "USD",
}
_MARKET_BY_CURRENCY = {"GBP": "UK", "EUR": "EU", "USD": "US"}
_MARKET_KEYWORDS = {
    "uk": "UK",
    "united kingdom": "UK",
    "britain": "UK",
    "us": "US",
    "usa": "US",
    "united states": "US",
    "eu": "EU",
    "europe": "EU",
}

_NUMBER_OF_PRODUCTS_RE = re.compile(
    r"\b(\d{1,2})\s+(?:[a-z][a-z-]*[,]?\s+){0,4}(?:products?|items?|ideas?|concepts?)\b",
    re.IGNORECASE,
)
_BUDGET_RE = re.compile(r"[£€$]\s?(\d+(?:\.\d{1,2})?)|(\d+(?:\.\d{1,2})?)\s?(?:gbp|eur|usd|pounds?|euros?|dollars?)", re.IGNORECASE)
_MARGIN_RE = re.compile(
    r"(?:at least|min(?:imum)?|>=?)\s*(\d{1,3})\s?%\s*margin|margin\s*(?:of\s*)?(?:at least|>=?)?\s*(\d{1,3})\s?%",
    re.IGNORECASE,
)
_ROI_RE = re.compile(r"(?:at least|min(?:imum)?|>=?)\s*(\d{1,3})\s?%\s*roi", re.IGNORECASE)

_RISK_HIGH_WORDS = ("aggressive", "high risk", "high-risk")
_RISK_LOW_WORDS = ("conservative", "low risk", "low-risk", "safe", "cautious")


@dataclass
class SearchCriteria:
    """Structured constraints parsed out of a free-text search request.

    These drive *how* candidates are generated (count, currency, price range) —
    they are constraints on the search, never content for a product name.
    """

    currency: str = "USD"
    market: str | None = None
    budget: float | None = None
    number_of_products: int = DEFAULT_NUMBER_OF_PRODUCTS
    min_margin_pct: float | None = None
    min_roi_pct: float | None = None
    risk_tolerance: str = "Moderate"
    preferred_categories: list[str] = field(default_factory=list)
    excluded_categories: list[str] = field(default_factory=list)
    maximum_unit_cost: float | None = None
    marketplace: str | None = None
    sourcing_region: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SearchCriteria":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def to_provider_filters(self, extra: dict | None = None) -> dict:
        """Shape a search provider actually reads (see `SearchProvider.search_products`)."""

        provider_filters = {
            "number_of_products": self.number_of_products,
            "currency": self.currency,
            "budget": self.budget,
            "preferred_categories": self.preferred_categories,
        }
        if extra:
            provider_filters.update(extra)
        return provider_filters


def _detect_currency(query: str) -> str | None:
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol in query:
            return code
    lowered = query.lower()
    for word, code in _CURRENCY_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            return code
    return None


def _detect_market(query: str, currency: str | None) -> str | None:
    lowered = query.lower()
    for keyword, market in _MARKET_KEYWORDS.items():
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            return market
    if currency:
        return _MARKET_BY_CURRENCY.get(currency)
    return None


def _detect_budget(query: str) -> float | None:
    match = _BUDGET_RE.search(query)
    if not match:
        return None
    raw = match.group(1) or match.group(2)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _detect_number_of_products(query: str) -> int:
    match = _NUMBER_OF_PRODUCTS_RE.search(query)
    if not match:
        return DEFAULT_NUMBER_OF_PRODUCTS
    return max(1, min(int(match.group(1)), MAX_NUMBER_OF_PRODUCTS))


def _search_pct(pattern: re.Pattern, query: str) -> float | None:
    match = pattern.search(query)
    if not match:
        return None
    raw = next((g for g in match.groups() if g), None)
    return float(raw) if raw is not None else None


def _find_margin(query: str) -> float | None:
    return _search_pct(_MARGIN_RE, query)


def _find_roi(query: str) -> float | None:
    return _search_pct(_ROI_RE, query)


def _detect_risk_tolerance(query: str) -> str:
    lowered = query.lower()
    if any(word in lowered for word in _RISK_HIGH_WORDS):
        return "High"
    if any(word in lowered for word in _RISK_LOW_WORDS):
        return "Low"
    return "Moderate"


def parse_search_criteria(query: str, filters: dict | None = None) -> SearchCriteria:
    """Parses `query` into `SearchCriteria`, with `filters` (from the API request)
    taking precedence over anything inferred from the free text.
    """

    filters = filters or {}

    currency = filters.get("currency") or _detect_currency(query) or "USD"
    market = filters.get("market") or _detect_market(query, currency)
    budget = filters.get("budget") if filters.get("budget") is not None else _detect_budget(query)
    number_of_products = int(filters.get("number_of_products") or filters.get("limit") or _detect_number_of_products(query))
    number_of_products = max(1, min(number_of_products, MAX_NUMBER_OF_PRODUCTS))
    min_margin_pct = filters.get("min_margin_pct") if filters.get("min_margin_pct") is not None else _find_margin(query)
    min_roi_pct = filters.get("min_roi_pct") if filters.get("min_roi_pct") is not None else _find_roi(query)
    risk_tolerance = filters.get("risk_tolerance") or _detect_risk_tolerance(query)
    max_unit_cost = filters.get("maximum_unit_cost")
    if max_unit_cost is None and budget is not None and number_of_products:
        # A simple, explicit heuristic (not a business rule elsewhere): a unit cost
        # above the whole test budget clearly isn't test-purchasable, so cap it there.
        max_unit_cost = budget

    return SearchCriteria(
        currency=currency,
        market=market,
        budget=budget,
        number_of_products=number_of_products,
        min_margin_pct=min_margin_pct,
        min_roi_pct=min_roi_pct,
        risk_tolerance=risk_tolerance,
        preferred_categories=filters.get("preferred_categories") or [],
        excluded_categories=filters.get("excluded_categories") or [],
        maximum_unit_cost=max_unit_cost,
        marketplace=filters.get("marketplace"),
        sourcing_region=filters.get("sourcing_region"),
    )


def get_or_parse_criteria(query: str, filters: dict | None) -> SearchCriteria:
    """Reuses already-parsed criteria (stored under `filters["parsed_criteria"]` by
    the run orchestrator) instead of re-parsing, so display and generation always
    agree on the same criteria for a given run.
    """

    filters = filters or {}
    stored = filters.get("parsed_criteria")
    if isinstance(stored, dict):
        return SearchCriteria.from_dict(stored)
    return parse_search_criteria(query, filters)
