"""Small render/formatting helpers shared across pages — keeps decision colors,
status colors, currency and interpretation consistent everywhere without
duplicating markup or logic per page.
"""

from typing import Any

import streamlit as st

_DECISION_STYLE = {
    "BUY_TEST": ("#1a7f37", "#dafbe1", "STRONG OPPORTUNITY — TEST"),
    "WATCH": ("#9a6700", "#fff8c5", "WATCH"),
    "REJECT": ("#cf222e", "#ffebe9", "REJECT"),
}
_NOT_EVALUATED_STYLE = ("#57606a", "#eaeef2", "NOT YET EVALUATED")

_RUN_STATUS_STYLE = {
    "PENDING": ("#57606a", "#eaeef2", "PENDING"),
    "RUNNING": ("#0969da", "#ddf4ff", "RUNNING"),
    "COMPLETE": ("#1a7f37", "#dafbe1", "COMPLETE"),
    "FAILED": ("#cf222e", "#ffebe9", "FAILED"),
}

_DATA_QUALITY_STYLE = {
    "DEMO": ("#9a6700", "#fff8c5", "DEMO DATA"),
    "LIVE": ("#1a7f37", "#dafbe1", "LIVE DATA"),
}

_APPROVAL_STATUS_STYLE = {
    "PENDING": ("#57606a", "#eaeef2", "PENDING"),
    "SENT": ("#1a7f37", "#dafbe1", "SENT TO OPERATIONS"),
    "FAILED": ("#cf222e", "#ffebe9", "FAILED — RETRY AVAILABLE"),
}

_CURRENCY_SYMBOLS = {"USD": "$", "GBP": "£", "EUR": "€"}

# (low threshold exclusive upper bound, label) — evaluated low to high.
_LEVEL_BANDS = [(34, "Low"), (67, "Medium")]


def _badge_html(color: str, bg: str, label: str) -> str:
    return (
        f'<span style="background:{bg};color:{color};padding:2px 10px;'
        f'border-radius:999px;font-weight:600;font-size:0.85rem;white-space:nowrap;">{label}</span>'
    )


def decision_badge(decision: str | None) -> None:
    color, bg, label = _DECISION_STYLE.get(decision, _NOT_EVALUATED_STYLE)
    st.markdown(_badge_html(color, bg, label), unsafe_allow_html=True)


def run_status_badge(status: str) -> None:
    color, bg, label = _RUN_STATUS_STYLE.get(status, ("#57606a", "#eaeef2", status))
    st.markdown(_badge_html(color, bg, label), unsafe_allow_html=True)


def data_quality_badge(data_quality: str) -> None:
    color, bg, label = _DATA_QUALITY_STYLE.get(data_quality, ("#57606a", "#eaeef2", data_quality))
    st.markdown(_badge_html(color, bg, label), unsafe_allow_html=True)


def approval_status_badge(status: str) -> None:
    color, bg, label = _APPROVAL_STATUS_STYLE.get(status, ("#57606a", "#eaeef2", status))
    st.markdown(_badge_html(color, bg, label), unsafe_allow_html=True)


def format_currency(value: float | None, currency: str = "USD") -> str:
    if value is None:
        return "—"
    symbol = _CURRENCY_SYMBOLS.get(currency, f"{currency} ")
    return f"{symbol}{value:,.2f}"


def format_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}%"


def _level_label(score: float) -> str:
    for threshold, label in _LEVEL_BANDS:
        if score < threshold:
            return label
    return "High"


def interpret_demand(score: float) -> tuple[str, str]:
    """Returns (label, tone) for a demand score. Higher demand is favourable, so
    tone tracks the score directly: High -> good, Low -> caution.
    """

    label = _level_label(score)
    tone = {"Low": "bad", "Medium": "neutral", "High": "good"}[label]
    return label, tone


def interpret_competition(score: float) -> tuple[str, str]:
    """Returns (label, tone) for a competition score. Higher competition is *less*
    favourable, so tone is the inverse of demand's: High -> caution, Low -> good.
    """

    label = _level_label(score)
    tone = {"Low": "good", "Medium": "neutral", "High": "bad"}[label]
    return label, tone


_TONE_COLORS = {
    "good": "#1a7f37",
    "neutral": "#9a6700",
    "bad": "#cf222e",
}


def level_metric(label: str, score: float, tone: str) -> None:
    """A demand/competition style metric that shows both the number *and* what it
    means (e.g. "High · 83/100") rather than a bare number a reader has to
    interpret themselves — and colors it by favourability, not just magnitude, so
    a high competition score doesn't get the same "this is good" green as a high
    demand score.
    """

    color = _TONE_COLORS[tone]
    interpretation = _level_label(score)
    st.markdown(
        f'<div style="font-size:0.8rem;color:var(--text-color,#8a8f98);margin-bottom:2px;">{label}</div>'
        f'<div style="font-size:1.1rem;font-weight:600;color:{color};">'
        f"{interpretation} · {score:.0f}/100</div>",
        unsafe_allow_html=True,
    )


def money_metric(label: str, value: float | None, currency: str = "USD") -> None:
    """A monetary value rendered as sized text rather than `st.metric` — `st.metric`
    truncates its value with an ellipsis when the column is narrower than the
    formatted string (the "$5..." bug), which a bold text block wraps instead of
    ever truncating.
    """

    st.markdown(
        f'<div style="font-size:0.8rem;color:var(--text-color,#8a8f98);margin-bottom:2px;">{label}</div>'
        f'<div style="font-size:1.1rem;font-weight:600;">{format_currency(value, currency)}</div>',
        unsafe_allow_html=True,
    )


def build_why_recommended(opportunity: dict) -> str:
    """A short, deterministic explanation built only from fields the API actually
    returned for this opportunity — never fabricated, and it says so plainly when
    the commercial numbers aren't available yet.
    """

    demand_label, _ = interpret_demand(opportunity["demand_score"])
    competition_label, _ = interpret_competition(opportunity["competition_score"])
    demand_phrase = {
        "High": "strong demand",
        "Medium": "moderate demand",
        "Low": "limited demand",
    }[demand_label]
    competition_phrase = {
        "Low": "low competition",
        "Medium": "moderate competition",
        "High": "high competition",
    }[competition_label]

    best_offer = opportunity.get("best_offer")
    if best_offer is None:
        return (
            f"{demand_phrase.capitalize()} and {competition_phrase} based on discovery-stage "
            "evidence. Supplier sourcing and profitability haven't run for this opportunity yet, "
            "so there's no margin/ROI figure to weigh in."
        )

    margin = best_offer["margin_pct"]
    roi = best_offer["roi_pct"]
    return (
        f"{demand_phrase.capitalize()} and {competition_phrase}, with an estimated "
        f"{margin:.0f}% margin and {roi:.0f}% ROI on the best-priced supplier offer found."
    )


def api_error_banner(exc: Any) -> None:
    st.error(getattr(exc, "message", str(exc)))
    details = getattr(exc, "details", None)
    if details:
        with st.expander("Details"):
            st.json(details)
