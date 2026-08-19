"""Deterministic guardrails on generated product titles.

This is the fix for the "search query leaks into the product name" bug: rather
than trusting a generator (mock catalog today, potentially an LLM later) to never
echo the request back, every title is checked here before it's persisted. Pure
functions, no I/O — same pattern as `ranking.py` / `calculator.py`.
"""

import re

MIN_TITLE_LENGTH = 3
MAX_TITLE_LENGTH = 80

# Phrases that mark a string as an instruction/request rather than a product name.
_INSTRUCTION_PATTERNS = [
    re.compile(r"\bfind\s+\d+\b", re.IGNORECASE),
    re.compile(r"\bsuitable\s+for\b", re.IGNORECASE),
    re.compile(r"\btest\s+budget\b", re.IGNORECASE),
    re.compile(r"\bbudget\b", re.IGNORECASE),
    re.compile(r"\b\d+\s*%\s*margin\b", re.IGNORECASE),
    re.compile(r"[£€$]\s?\d", re.IGNORECASE),
    re.compile(r"\byou\s+(are|must|should)\b", re.IGNORECASE),
    re.compile(r"\bplease\b", re.IGNORECASE),
    re.compile(r"\bproducts?\s+(suitable|for|with)\b", re.IGNORECASE),
]

_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "the", "for", "with", "and", "or", "in", "on", "at", "to", "of",
    "find", "suitable", "product", "products", "item", "items",
}


def _significant_tokens(text: str) -> set[str]:
    return {t for t in _WORD_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 2}


def is_valid_product_title(title: str, query: str) -> tuple[bool, str | None]:
    """Returns (is_valid, reason_if_not).

    Rejects titles that are too short/long, read as an instruction rather than a
    product, or substantially repeat the search request's own wording.
    """

    title = (title or "").strip()

    if len(title) < MIN_TITLE_LENGTH:
        return False, "too short"
    if len(title) > MAX_TITLE_LENGTH:
        return False, "too long"

    for pattern in _INSTRUCTION_PATTERNS:
        if pattern.search(title):
            return False, f"reads as an instruction (matched {pattern.pattern!r})"

    query_tokens = _significant_tokens(query)
    title_tokens = _significant_tokens(title)
    if query_tokens and title_tokens:
        overlap = len(query_tokens & title_tokens) / len(query_tokens)
        # Half or more of the query's own meaningful words showing up verbatim in
        # the title is the signature of "the query got pasted into the title" —
        # a genuine product name for that query will share at most a couple of
        # generic nouns, not the majority of the request's own wording.
        if overlap >= 0.5:
            return False, f"repeats {overlap:.0%} of the search query's wording"

    return True, None


def _normalize_for_dedupe(title: str) -> frozenset[str]:
    return frozenset(_significant_tokens(title))


def find_duplicate_indices(titles: list[str], *, similarity_threshold: float = 0.8) -> set[int]:
    """Indices of titles that are a near-duplicate of an earlier one in the list
    (by token-set (Jaccard) similarity), so callers can drop repeats within one
    generated batch.
    """

    seen: list[frozenset[str]] = []
    duplicates: set[int] = set()
    for index, title in enumerate(titles):
        tokens = _normalize_for_dedupe(title)
        is_duplicate = any(
            tokens and other and len(tokens & other) / len(tokens | other) >= similarity_threshold
            for other in seen
        )
        if is_duplicate:
            duplicates.add(index)
        seen.append(tokens)
    return duplicates
