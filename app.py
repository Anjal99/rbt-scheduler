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

# ── Auto-load from local Excel if present (dev only) ──
EXCEL_PATH = os.path.join(os.path.dirname(__file__), 'RBT + Client Schedule.xlsx')

if os.path.exists(EXCEL_PATH):
    if therapist_count() == 0:
        try:
            tdf = pd.read_excel(EXCEL_PATH, sheet_name='Therapists')
            bulk_import_therapists(tdf)
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

# ── Upload section (shown when data is missing) ──
t_count = therapist_count()
c_count = len(st.session_state.get('clients_df', []))
has_schedule = st.session_state.get('schedule_generated', False)

if t_count == 0 or c_count == 0:
    st.markdown("### Upload Your Schedule File")
    st.markdown(
        "Upload your Excel file containing both **Therapists** and **Clients** sheets. "
        "The app will load both automatically."
    )

    uploaded = st.file_uploader(
        "Choose your Excel file (.xlsx)",
        type=["xlsx"],
        key="home_upload",
        label_visibility="collapsed",
    )

    if uploaded:
        try:
            xl = pd.ExcelFile(uploaded)
            sheets = xl.sheet_names
            loaded = []

            # Load Therapists
            t_sheet = next((s for s in sheets if 'therapist' in s.lower()), None)
            if t_sheet:
                tdf = pd.read_excel(uploaded, sheet_name=t_sheet)
                count = bulk_import_therapists(tdf)
                loaded.append(f"{count} therapists from '{t_sheet}'")

            # Load Clients
            c_sheet = next((s for s in sheets if 'client' in s.lower()), None)
            if c_sheet:
                uploaded.seek(0)
                cdf = pd.read_excel(uploaded, sheet_name=c_sheet)
                st.session_state['clients_df'] = cdf
                st.session_state['clients_uploaded'] = True
                loaded.append(f"{len(cdf)} clients from '{c_sheet}'")

            if loaded:
                st.success(f"Loaded: {', '.join(loaded)}")
                # Clear any stale schedule
                st.session_state.pop('schedule_generated', None)
                st.session_state.pop('assignments_df', None)
                st.rerun()
            else:
                st.warning("Could not find 'Therapists' or 'Clients' sheets in the file.")

        except Exception as e:
            st.error(f"Error reading file: {e}")

    st.markdown("---")

# ── Status overview ──
t_count = therapist_count()
c_count = len(st.session_state.get('clients_df', []))

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
elif t_count > 0 and c_count > 0:
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Therapists", t_count)
    with c2:
        st.metric("Clients", c_count)

    st.markdown("")
    st.info("Data loaded! Go to **Schedule** to generate the weekly schedule.")
    st.page_link("pages/3_schedule.py", label="Generate Schedule", icon="📅")

st.markdown("")

# ── Quick start cards ──
st.markdown("### Pages")
col1, col2, col3 = st.columns(3)

with col1:
    info_card(
        "👥", "Manage Therapists",
        "Add, edit, and remove therapists from your roster. "
        "Set availability, in-home capability, and workload preferences."
    )
    st.page_link("pages/1_therapists.py", label="Manage Therapists", icon="👥")

with col2:
    info_card(
        "📄", "Upload Clients",
        "Upload or replace your client/patient list. "
        "You can also upload the full Excel here to load both sheets."
    )
    st.page_link("pages/2_upload_clients.py", label="Upload Clients", icon="📄")

with col3:
    info_card(
        "📅", "Schedule",
        "Generate the weekly schedule, view the timetable, "
        "and export to Excel or CSV."
    )
    st.page_link("pages/3_schedule.py", label="Schedule", icon="📅")

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
