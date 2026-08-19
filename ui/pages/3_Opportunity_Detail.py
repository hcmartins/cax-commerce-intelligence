import streamlit as st

from api_client import (
    ApiError,
    approve_opportunity,
    get_opportunity,
    list_opportunity_approvals,
    list_opportunity_profitability,
    list_opportunity_suppliers,
    recalculate_profitability,
)
from components import (
    api_error_banner,
    approval_status_badge,
    data_quality_badge,
    decision_badge,
    format_currency,
    format_pct,
    interpret_competition,
    interpret_demand,
    money_metric,
)

opportunity_id = st.query_params.get("opportunity_id") or st.session_state.get(
    "current_opportunity_id"
)
if not opportunity_id:
    st.warning("No opportunity selected.")
    st.page_link("pages/2_Opportunities.py", label="← Back to opportunities", icon="📊")
    st.stop()

st.session_state["current_opportunity_id"] = opportunity_id
st.query_params["opportunity_id"] = opportunity_id  # bookmarkable/shareable URL

try:
    opportunity = get_opportunity(opportunity_id)
    suppliers = list_opportunity_suppliers(opportunity_id)
    calculations = list_opportunity_profitability(opportunity_id)
except ApiError as exc:
    api_error_banner(exc)
    st.stop()

st.page_link("pages/2_Opportunities.py", label="← Back to opportunities", icon="📊")

# --- Opportunity Summary ---
header_cols = st.columns([4, 2, 2])
with header_cols[0]:
    st.title(opportunity["title"])
    st.caption(opportunity.get("category") or "Uncategorized")
with header_cols[1]:
    decision_badge(opportunity["best_offer"]["decision"] if opportunity["best_offer"] else None)
with header_cols[2]:
    data_quality_badge(opportunity["data_quality"])

summary_cols = st.columns(4)
summary_cols[0].metric("Rank", f"#{opportunity['rank']}" if opportunity["rank"] else "—")
summary_cols[1].metric("Opportunity score", f"{opportunity['overall_score']:.0f}/100")
summary_cols[2].metric("Trend", f"{opportunity['trend_score']:.0f}/100")
with summary_cols[3]:
    money_metric("Observed market price", opportunity["avg_selling_price"], opportunity["currency"])

st.divider()

# --- Market Evidence ---
st.subheader("Market Evidence")
evidence = opportunity.get("raw_evidence", {})
ev_cols = st.columns(4)
with ev_cols[0]:
    label, tone = interpret_demand(opportunity["demand_score"])
    st.metric("Demand", f"{label} · {opportunity['demand_score']:.0f}/100")
with ev_cols[1]:
    label, tone = interpret_competition(opportunity["competition_score"])
    st.metric("Competition", f"{label} · {opportunity['competition_score']:.0f}/100")
ev_cols[2].metric("Trend direction", evidence.get("trend_direction", "—").capitalize() or "—")
ev_cols[3].metric("Monthly search volume", f"{evidence.get('monthly_search_volume', 0):,}")
st.caption(
    f"Active sellers observed: {evidence.get('active_sellers', '—')} · "
    f"Source: {opportunity['source']} · Evidence recorded: {opportunity['created_at'][:19]}"
)
with st.expander("Raw evidence payload"):
    st.json(evidence)

st.divider()

# --- Supplier Intelligence ---
st.subheader(f"Supplier Intelligence ({len(suppliers)} offers)")

if not suppliers:
    st.info("No supplier offers found for this opportunity.")
else:
    for offer in suppliers:
        supplier = offer["supplier"]
        with st.container(border=True):
            cols = st.columns([2, 1, 1, 1, 1, 2])
            cols[0].markdown(f"**{supplier['name']}**  \n{supplier.get('country') or 'Unknown'}")
            with cols[1]:
                money_metric("Unit price", offer["unit_price"], offer["currency"])
            cols[2].metric("MOQ", offer["moq"])
            lead_time = f"{offer['lead_time_days']}d" if offer["lead_time_days"] else "—"
            cols[3].metric("Lead time", lead_time)
            with cols[4]:
                money_metric("Shipping", offer.get("shipping_cost"), offer["currency"])
            contact_bits = [c for c in [supplier.get("contact_email"), supplier.get("contact_phone")] if c]
            cols[5].markdown("  \n".join(contact_bits) or "No contact on file")

st.divider()

# --- Profit Analysis ---
st.subheader("Profit Analysis")

if not calculations:
    st.info("No profitability calculations yet — supplier sourcing hasn't produced an offer to price.")
else:
    for calc in calculations:
        with st.container(border=True):
            top = st.columns(5)
            with top[0]:
                money_metric("Landed cost", calc["landed_cost"], calc["currency"])
            with top[1]:
                money_metric("Selling price", calc["selling_price"], calc["currency"])
            with top[2]:
                money_metric("Profit / unit", calc["profit"], calc["currency"])
            top[3].metric("Margin", format_pct(calc["margin_pct"]))
            top[4].metric("ROI", format_pct(calc["roi_pct"]))

            with st.expander("Cost breakdown"):
                bcols = st.columns(3)
                with bcols[0]:
                    money_metric("Marketplace fee", calc["marketplace_fee"], calc["currency"])
                with bcols[1]:
                    money_metric("Shipping (per unit share)", calc["shipping_cost"], calc["currency"])
                with bcols[2]:
                    money_metric("Other costs", calc["other_costs"], calc["currency"])

            rec = calc.get("recommendation")
            if rec:
                decision_badge(rec["decision"])
                st.write(rec["rationale"])

st.divider()

# --- Risks ---
st.subheader("Risks")
risks: list[str] = []
if opportunity["competition_score"] >= 67:
    risks.append(f"High competition ({opportunity['competition_score']:.0f}/100) may compress margin over time.")
if evidence.get("trend_direction") == "declining":
    risks.append("Trend evidence shows a declining direction — demand may not be durable.")
if not suppliers:
    risks.append("No supplier offers found — sourcing viability is unconfirmed.")
best_offer = opportunity.get("best_offer")
if best_offer and best_offer["margin_pct"] < 15:
    risks.append(f"Thin margin ({best_offer['margin_pct']:.1f}%) leaves little room for cost increases.")
if opportunity["data_quality"] == "DEMO":
    risks.append(
        "This opportunity is based on the MVP's deterministic demo data, not verified live "
        "marketplace intelligence — treat all figures above as illustrative, not confirmed."
    )
if not risks:
    risks.append("No specific risk flags raised from the available evidence.")
for risk in risks:
    st.markdown(f"- {risk}")

st.divider()

# --- Decision ---
st.subheader("Decision")
if best_offer:
    decision_badge(best_offer["decision"])
    rec = next((c["recommendation"] for c in calculations if c.get("recommendation")), None)
    if rec:
        st.write(rec["rationale"])

    st.markdown("##### Approve for Operations")
    st.caption(
        "Sends this opportunity's approved commercial case to the Commerce Operations "
        "platform (procurement, inventory, listing, orders) — a separate system this "
        "app doesn't implement itself."
    )

    try:
        approvals = list_opportunity_approvals(opportunity_id)
    except ApiError as exc:
        approvals = []
        api_error_banner(exc)

    if approvals:
        latest = approvals[0]
        approval_status_badge(latest["status"])
        if latest["status"] == "SENT":
            st.caption(f"Reference: {latest['external_reference']}")
        elif latest["status"] == "FAILED":
            st.caption(f"Last attempt failed: {latest['error_message']}")

    button_label = "Retry approval" if approvals and approvals[0]["status"] == "FAILED" else "Approve for Operations"
    if st.button(button_label, type="primary"):
        try:
            result = approve_opportunity(opportunity_id)
        except ApiError as exc:
            api_error_banner(exc)
        else:
            if result["status"] == "SENT":
                st.success(f"Sent to Operations — reference {result['external_reference']}.")
            else:
                st.error(f"Approval failed: {result['error_message']}. State was preserved — retry above.")
else:
    st.info(
        "This opportunity hasn't been through supplier sourcing and profitability yet, so there's "
        "no BUY/WATCH/REJECT call to show — only the top-ranked opportunities per run are evaluated."
    )

st.divider()
st.subheader("Try different assumptions")
st.caption("Recalculate profitability for one supplier offer without starting a new search.")

if suppliers:
    offer_options = {
        f"{o['supplier']['name']} — {format_currency(o['unit_price'], o['currency'])}": o["id"]
        for o in suppliers
    }
    with st.form("recalculate_form"):
        offer_label = st.selectbox("Supplier offer", list(offer_options.keys()))
        selling_price = st.number_input(
            "Selling price override",
            min_value=0.01,
            value=float(opportunity["avg_selling_price"]) or 1.0,
        )
        fee_pct = st.number_input("Marketplace fee % override", min_value=0.0, value=15.0)
        recalc_submitted = st.form_submit_button("Recalculate")

    if recalc_submitted:
        try:
            result = recalculate_profitability(
                opportunity_id,
                supplier_offer_id=offer_options[offer_label],
                selling_price=selling_price,
                marketplace_fee_pct=fee_pct,
            )
        except ApiError as exc:
            api_error_banner(exc)
        else:
            st.success("Recalculated.")
            cols = st.columns(5)
            with cols[0]:
                money_metric("Landed cost", result["landed_cost"], result["currency"])
            with cols[1]:
                money_metric("Selling price", result["selling_price"], result["currency"])
            with cols[2]:
                money_metric("Profit / unit", result["profit"], result["currency"])
            cols[3].metric("Margin", format_pct(result["margin_pct"]))
            cols[4].metric("ROI", format_pct(result["roi_pct"]))
            if result.get("recommendation"):
                decision_badge(result["recommendation"]["decision"])
                st.write(result["recommendation"]["rationale"])
            st.caption("Reopen this page to see the new calculation listed above.")
