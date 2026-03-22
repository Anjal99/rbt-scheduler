"""
Therapy Scheduler Pro — Home Page
"""

import streamlit as st
import pandas as pd
import os

from utils.database import get_all_therapists, bulk_import_therapists, therapist_count, init_db
from utils.styles import apply_global_styles, sidebar_nav, page_header, info_card

st.set_page_config(
    page_title="Therapy Scheduler Pro",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_styles()

# ── Auto-load Excel data on first run ──
EXCEL_PATH = os.path.join(os.path.dirname(__file__), 'RBT + Client Schedule.xlsx')

if os.path.exists(EXCEL_PATH):
    if therapist_count() == 0:
        try:
            tdf = pd.read_excel(EXCEL_PATH, sheet_name='Therapists')
            count = bulk_import_therapists(tdf)
            if count > 0:
                st.toast(f"Auto-imported {count} therapists from Excel")
        except Exception:
            pass

    if not st.session_state.get('clients_uploaded'):
        try:
            cdf = pd.read_excel(EXCEL_PATH, sheet_name='Clients')
            st.session_state['clients_df'] = cdf
            st.session_state['clients_uploaded'] = True
        except Exception:
            pass

# ── Sidebar ──
sidebar_nav()

# ── Main Content ──
page_header("Therapy Scheduler Pro", "Automated weekly scheduling for your therapy clinic")

# Status overview
t_count = therapist_count()
c_count = len(st.session_state.get('clients_df', []))
has_schedule = st.session_state.get('schedule_generated', False)

if has_schedule:
    stats = st.session_state.get('schedule_stats', {})
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Therapists", t_count)
    with c2:
        st.metric("Clients", c_count)
    with c3:
        st.metric("Coverage", f"{stats.get('coverage_pct', 0):.0f}%")
    with c4:
        st.metric("Assignments", stats.get('total_assignments', 0))

    st.markdown("")
    st.success("Schedule is generated! Go to the **Schedule** page to view and export it.")
    st.page_link("pages/3_schedule.py", label="View Schedule", icon="📅")
else:
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Therapists", t_count)
    with c2:
        st.metric("Clients", c_count)

st.markdown("")

# ── Quick start cards ──
st.markdown("### Get Started")
col1, col2, col3 = st.columns(3)

with col1:
    info_card(
        "👥", "1. Manage Therapists",
        "Add, edit, and remove therapists from your roster. "
        "Set availability, in-home capability, and workload preferences."
    )
    st.page_link("pages/1_therapists.py", label="Manage Therapists", icon="👥")

with col2:
    info_card(
        "📄", "2. Upload Clients",
        "Upload your client/patient list as an Excel file. "
        "We'll parse schedules, intensity levels, and location needs."
    )
    st.page_link("pages/2_upload_clients.py", label="Upload Clients", icon="📄")

with col3:
    info_card(
        "📅", "3. Generate Schedule",
        "Generate an optimized weekly schedule that respects all "
        "intensity caps, breaks, travel buffers, and workload limits."
    )
    st.page_link("pages/3_schedule.py", label="Generate Schedule", icon="📅")

# ── Rules summary ──
st.markdown("")
with st.expander("Scheduling Rules Reference"):
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
        **Hard Constraints**
        - No therapist double-booking (overlaps)
        - 30-min break required every 4 hours
        - High intensity: max 3h continuous per therapist
        - Low intensity: max 4h continuous per therapist
        - 30-min travel buffer between in-home sessions
        """)
    with col_b:
        st.markdown("""
        **Workload Limits**
        - Soft cap: 30h/week (warning)
        - Hard cap: 35h/week (high warning)
        - 40h only if therapist is eligible
        - 40h requires 2-hour mid-day break
        - Preferred max hours respected per therapist
        """)
