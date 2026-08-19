import streamlit as st

from api_client import ApiError, get_run, list_run_opportunities, list_runs
from components import (
    build_why_recommended,
    data_quality_badge,
    decision_badge,
    interpret_competition,
    interpret_demand,
    level_metric,
    money_metric,
)

st.title("Ranked Opportunities")

requested_run_id = st.query_params.get("run_id") or st.session_state.get("current_run_id")

try:
    runs = list_runs(limit=50)
except ApiError as exc:
    st.error(f"Could not load runs: {exc.message}")
    st.stop()

completed_runs = [r for r in runs if r["status"] == "COMPLETE"]
if not completed_runs:
    st.info("No completed runs yet. Start a search first.")
    st.page_link("pages/1_New_Search.py", label="Start a new search →", icon="🔍")
    st.stop()

options = {
    f"{r['query_text']} — {r['id'][:8]} ({r['created_at'][:19]})": r["id"] for r in completed_runs
}
labels = list(options.keys())
default_index = 0
if requested_run_id:
    for i, rid in enumerate(options.values()):
        if rid == requested_run_id:
            default_index = i
            break

selected_label = st.selectbox("Run", labels, index=default_index)
run_id = options[selected_label]
st.query_params["run_id"] = run_id
st.session_state["current_run_id"] = run_id

try:
    run = get_run(run_id)
    opportunities = list_run_opportunities(run_id)
except ApiError as exc:
    st.error(f"Could not load this run: {exc.message}")
    st.stop()

# --- Search run header: the original request and how it was understood, shown
# once here rather than repeated inside every card below. ---
with st.container(border=True):
    st.markdown("##### Search")
    st.markdown(f"“{run['query_text']}”")
    criteria = run.get("filters", {}).get("parsed_criteria")
    if criteria:
        cols = st.columns(5)
        cols[0].markdown(f"**Market**  \n{criteria.get('market') or '—'}")
        cols[1].markdown(f"**Currency**  \n{criteria['currency']}")
        budget = criteria.get("budget")
        cols[2].markdown(f"**Budget**  \n{criteria['currency'] + ' ' + f'{budget:.0f}' if budget else '—'}")
        cols[3].markdown(f"**Products requested**  \n{criteria['number_of_products']}")
        cols[4].markdown(f"**Risk**  \n{criteria['risk_tolerance']}")

if not opportunities:
    st.warning("This run didn't produce any opportunities.")
    st.stop()

st.caption(
    f"{len(opportunities)} candidates found, ranked by demand/competition/trend. "
    "The top-ranked opportunities have also been through supplier sourcing and profitability — "
    "look for the commercial metrics below."
)

for opp in opportunities:
    with st.container(border=True):
        header_cols = st.columns([4, 2, 2])
        with header_cols[0]:
            st.markdown(f"**#{opp['rank']} · {opp['title']}**")
            st.caption(opp.get("category") or "Uncategorized")
        with header_cols[1]:
            decision = opp["best_offer"]["decision"] if opp["best_offer"] else None
            decision_badge(decision)
        with header_cols[2]:
            data_quality_badge(opp["data_quality"])

        metric_cols = st.columns(5)
        metric_cols[0].metric("Opportunity score", f"{opp['overall_score']:.0f}/100")
        with metric_cols[1]:
            label, tone = interpret_demand(opp["demand_score"])
            level_metric("Demand", opp["demand_score"], tone)
        with metric_cols[2]:
            label, tone = interpret_competition(opp["competition_score"])
            level_metric("Competition", opp["competition_score"], tone)

        best_offer = opp["best_offer"]
        if best_offer:
            with metric_cols[3]:
                money_metric("Landed cost", best_offer["landed_cost"], best_offer["currency"])
            with metric_cols[4]:
                money_metric("Selling price", best_offer["selling_price"], best_offer["currency"])

            profit_cols = st.columns(4)
            with profit_cols[0]:
                money_metric("Buy cost", best_offer["unit_price"], best_offer["currency"])
            with profit_cols[1]:
                money_metric("Profit / unit", best_offer["profit"], best_offer["currency"])
            profit_cols[2].metric("Margin", f"{best_offer['margin_pct']:.1f}%")
            profit_cols[3].metric("ROI", f"{best_offer['roi_pct']:.1f}%")
        else:
            with metric_cols[3]:
                money_metric("Market price", opp["avg_selling_price"], opp["currency"])
            metric_cols[4].caption("Supplier & profit data unavailable — not yet evaluated.")

        st.markdown(f"**Why:** {build_why_recommended(opp)}")

        if st.button("View full analysis →", key=f"view_{opp['id']}"):
            # st.switch_page() clears query_params entirely, so it can't carry the id
            # to the next page — session_state is what actually survives the switch.
            st.session_state["current_opportunity_id"] = opp["id"]
            st.switch_page("pages/3_Opportunity_Detail.py")
