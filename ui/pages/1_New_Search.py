import streamlit as st

from api_client import ApiError, start_run

st.title("New Search")
st.caption("Kick off product discovery → supplier sourcing → profitability → recommendation.")
st.caption(
    "Tip: describe your budget, currency/market, product count and target margin in plain "
    "language — e.g. *\"Find 10 lightweight products for a £200 UK test budget with at least "
    "30% margin\"* — and it'll be parsed into search criteria automatically."
)

with st.form("new_search_form"):
    query = st.text_input("What are you looking for?", placeholder="e.g. wireless earbuds")
    max_price = st.number_input("Max price (optional)", min_value=0.0, value=0.0, step=1.0)
    category = st.text_input("Category (optional)")
    submitted = st.form_submit_button("Run search", type="primary")

if submitted:
    if not query.strip():
        st.error("Enter something to search for.")
    else:
        filters = {}
        if max_price > 0:
            filters["max_price"] = max_price
        if category.strip():
            filters["category"] = category.strip()

        with st.spinner("Discovering opportunities, sourcing suppliers, calculating profitability..."):
            try:
                run = start_run(query.strip(), filters)
            except ApiError as exc:
                st.error(f"Search failed to start: {exc.message}")
            else:
                st.session_state["current_run_id"] = run["id"]
                if run["status"] == "COMPLETE":
                    st.success(f"Done — run {run['id'][:8]} completed.")

                    criteria = run.get("filters", {}).get("parsed_criteria")
                    if criteria:
                        st.markdown("**Understood as:**")
                        bits = [f"Market: {criteria['market']}" if criteria.get("market") else None]
                        bits.append(f"Currency: {criteria['currency']}")
                        if criteria.get("budget"):
                            bits.append(f"Budget: {criteria['currency']} {criteria['budget']:.0f}")
                        bits.append(f"Products requested: {criteria['number_of_products']}")
                        if criteria.get("min_margin_pct"):
                            bits.append(f"Min. margin: {criteria['min_margin_pct']:.0f}%")
                        bits.append(f"Risk tolerance: {criteria['risk_tolerance']}")
                        st.markdown(" · ".join(b for b in bits if b))

                    st.page_link(
                        "pages/2_Opportunities.py", label="View ranked opportunities →", icon="📊"
                    )
                else:
                    st.error(
                        f"Run finished as {run['status']}: "
                        f"{run.get('error_message') or 'no details available'}"
                    )
