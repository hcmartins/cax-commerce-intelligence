import streamlit as st

from api_client import ApiError, list_runs
from components import run_status_badge

st.title("Run History")

try:
    runs = list_runs(limit=50)
except ApiError as exc:
    st.error(f"Could not load runs: {exc.message}")
    st.stop()

if not runs:
    st.info("No searches yet.")
    st.page_link("pages/1_New_Search.py", label="Start a new search →", icon="🔍")
    st.stop()

for run in runs:
    with st.container(border=True):
        cols = st.columns([3, 1, 2, 1])
        cols[0].markdown(f"**{run['query_text']}**  \n`{run['id']}`")
        with cols[1]:
            run_status_badge(run["status"])
        finished = f"  \nFinished {run['completed_at'][:19]}" if run.get("completed_at") else ""
        cols[2].markdown(f"Started {run['created_at'][:19]}{finished}")
        if run["status"] == "COMPLETE":
            if cols[3].button("View", key=f"view_{run['id']}"):
                # st.switch_page() clears query_params entirely, so it can't carry the
                # id to the next page — session_state is what actually survives it.
                st.session_state["current_run_id"] = run["id"]
                st.switch_page("pages/2_Opportunities.py")
        elif run["status"] == "FAILED":
            cols[3].error(run.get("error_message") or "Failed")
