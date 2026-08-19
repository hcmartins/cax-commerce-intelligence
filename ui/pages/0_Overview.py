import streamlit as st

from api_client import ApiError, health_check

st.title("Commerce Intelligence")
st.caption("What should I sell, where should I buy it, and will it make money?")

try:
    health = health_check()
    if health.get("status") == "ok":
        st.success(f"Connected to the API — database {health.get('database', 'unknown')}.")
    else:
        st.warning(f"API reachable but reporting: {health}")
except ApiError as exc:
    st.error(f"Can't reach the API: {exc.message}")
    st.info("Start the backend with `uvicorn app.main:app --reload` and refresh this page.")

st.divider()

q1, q2, q3 = st.columns(3)
with q1:
    st.markdown("##### 🔍 What should I sell?")
    st.write("Discover and rank product opportunities from a plain-language search.")
with q2:
    st.markdown("##### 🌍 Where should I buy it?")
    st.write("Source candidate suppliers worldwide, with price, MOQ and lead time.")
with q3:
    st.markdown("##### 💰 Will it make money?")
    st.write("Land the true cost, compare it to market price, and get a BUY/WATCH/REJECT call.")

st.divider()

col1, col2 = st.columns(2)
with col1:
    st.subheader("Start here")
    st.write(
        "Search for a product idea and let the pipeline discover opportunities, "
        "source suppliers, and calculate profitability end to end."
    )
    st.page_link("pages/1_New_Search.py", label="Start a new search →", icon="🔍")
with col2:
    st.subheader("Past runs")
    st.write(
        "Review ranked opportunities, suppliers, and recommendations from previous searches."
    )
    st.page_link("pages/4_Run_History.py", label="View run history →", icon="🗂️")
