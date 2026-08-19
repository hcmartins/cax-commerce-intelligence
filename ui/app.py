import streamlit as st

st.set_page_config(page_title="Commerce Intelligence", page_icon="🧭", layout="wide")

# `st.navigation` (rather than relying on the legacy pages/ auto-discovery, which
# labels the sidebar entry for this file "app" — its filename minus the extension)
# gives every page an explicit, human-readable label instead.
pages = {
    "Intelligence": [
        st.Page("pages/0_Overview.py", title="Overview", icon="🧭", default=True),
        st.Page("pages/1_New_Search.py", title="New Search", icon="🔍"),
        st.Page("pages/2_Opportunities.py", title="Opportunities", icon="📊"),
        st.Page("pages/3_Opportunity_Detail.py", title="Opportunity Detail", icon="🔎"),
        st.Page("pages/4_Run_History.py", title="Run History", icon="🗂️"),
    ]
}

navigation = st.navigation(pages)
navigation.run()
