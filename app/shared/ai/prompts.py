"""Prompt templates shared by modules that call the AI client.

Kept as plain functions (not a templating engine) since the MVP only needs a
handful of short, single-purpose prompts.
"""

DECISION_RATIONALE_SYSTEM_PROMPT = (
    "You are a sourcing analyst for an e-commerce buying team. Given product, "
    "supplier and profitability data, write a concise (2-3 sentence) rationale for "
    "a BUY_TEST / WATCH / REJECT decision that has already been computed by a rules "
    "engine. Explain the *why* in plain business language. Do not change the decision."
)


def decision_rationale_prompt(
    *,
    product_title: str,
    decision: str,
    margin_pct: float,
    roi_pct: float,
    demand_score: float,
    competition_score: float,
) -> str:
    return (
        f"Product: {product_title}\n"
        f"Computed decision: {decision}\n"
        f"Margin: {margin_pct:.1f}%\n"
        f"ROI: {roi_pct:.1f}%\n"
        f"Demand score: {demand_score:.1f}/100\n"
        f"Competition score: {competition_score:.1f}/100\n\n"
        "Write the rationale."
    )
