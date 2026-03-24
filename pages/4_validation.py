"""
Validation Dashboard
"""

import streamlit as st
import pandas as pd

from utils.database import get_all_therapists
from utils.validators import validate_schedule
from utils.styles import apply_global_styles, sidebar_nav, page_header

st.set_page_config(page_title="Validation", page_icon="✅", layout="wide")
apply_global_styles()
sidebar_nav()

page_header("Validation", "Check your schedule for rule violations")

if not st.session_state.get('schedule_generated'):
    st.warning("No schedule to validate. Generate a schedule first.")
    st.page_link("pages/3_schedule.py", label="Generate Schedule", icon="📅")
    st.stop()

assignments_df = st.session_state['assignments_df']
clients_df = st.session_state.get('clients_df', pd.DataFrame())
therapists_df = get_all_therapists()

if assignments_df.empty:
    st.info("No assignments to validate.")
    st.stop()

# Run validation
flags = validate_schedule(assignments_df, therapists_df, clients_df)

errors = [f for f in flags if f['severity'] == 'Error']
crits = [f for f in flags if f['severity'] == 'Critical']
warns = [f for f in flags if f['severity'] == 'Warning']
infos = [f for f in flags if f['severity'] == 'Info']

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Errors", len(errors))
with c2:
    st.metric("Critical", len(crits))
with c3:
    st.metric("Warnings", len(warns))
with c4:
    st.metric("Info", len(infos))

st.markdown("---")

if not flags:
    st.success("All validations passed! No rule violations found.")
else:
    if crits:
        st.markdown("#### Critical")
        for f in crits:
            st.error(f"**{f['rule']}** — {f['who']} {f['day']}: {f['detail']}")

    if errors:
        st.markdown("#### Errors")
        for f in errors:
            st.error(f"**{f['rule']}** — {f['who']} {f['day']}: {f['detail']}")

    if warns:
        st.markdown("#### Warnings")
        for f in warns:
            st.warning(f"**{f['rule']}** — {f['who']} {f['day']}: {f['detail']}")

    if infos:
        with st.expander(f"Info ({len(infos)})"):
            for f in infos:
                st.info(f"**{f['rule']}** — {f['who']}: {f['detail']}")

    st.markdown("---")
    with st.expander("All flags as table"):
        st.dataframe(pd.DataFrame(flags), use_container_width=True, hide_index=True)
