"""
Client Upload Page
"""

import streamlit as st
import pandas as pd
from utils.styles import apply_global_styles, sidebar_nav, page_header

st.set_page_config(page_title="Upload Clients", page_icon="📄", layout="wide")
apply_global_styles()
sidebar_nav()

page_header("Upload Clients", "Upload your patient schedule as an Excel file")

# ── Currently loaded ──
if st.session_state.get('clients_uploaded'):
    df = st.session_state['clients_df']
    st.success(f"**{len(df)} clients** currently loaded")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Clients", len(df))
    with c2:
        if 'Intensity' in df.columns:
            st.metric("High Intensity", len(df[df['Intensity'].str.lower() == 'high']))
    with c3:
        if 'Intensity' in df.columns:
            st.metric("Low Intensity", len(df[df['Intensity'].str.lower() == 'low']))
    with c4:
        loc_col = next((c for c in df.columns if 'home' in c.lower() or 'in-home' in c.lower()), None)
        if loc_col:
            home_count = len(df[df[loc_col].str.lower().str.contains('home', na=False)])
            st.metric("In-Home / Hybrid", home_count)

    st.markdown("")
    st.dataframe(df, use_container_width=True, height=350, hide_index=True)
    st.markdown("")

st.markdown("---")

# ── Upload ──
st.markdown("### Upload New Client File")

with st.expander("Expected Excel format", expanded=False):
    st.markdown("""
    Your Excel should have a sheet named **Clients** with these columns:

    | Column | Example |
    |--------|---------|
    | Name | JoHa |
    | Schedule Needed | Mon-Fri 3pm - 7pm |
    | Days | Mon - Fri |
    | In-Home | Clinic / Home / Hybrid |
    | Travel notes | _(optional)_ |
    | Intensity | High / Low |
    | Notes | Hybrid: Mon, Wed In-Home; Tue, Thu Clinic |
    """)

uploaded = st.file_uploader(
    "Choose an Excel file (.xlsx)",
    type=["xlsx"],
    key="client_upload",
    label_visibility="collapsed"
)

if uploaded:
    try:
        xl = pd.ExcelFile(uploaded)
        client_sheet = None
        for name in xl.sheet_names:
            if 'client' in name.lower():
                client_sheet = name
                break
        if not client_sheet:
            client_sheet = st.selectbox("Select the sheet with client data:", xl.sheet_names)

        df = pd.read_excel(uploaded, sheet_name=client_sheet)
        st.success(f"Found **{len(df)} clients** in '{client_sheet}' sheet")
        st.dataframe(df, use_container_width=True, height=300, hide_index=True)

        if st.button("Load These Clients", type="primary", use_container_width=True):
            st.session_state['clients_df'] = df
            st.session_state['clients_uploaded'] = True
            # Clear any existing schedule since data changed
            st.session_state.pop('schedule_generated', None)
            st.session_state.pop('assignments_df', None)
            st.success("Client data loaded!")
            st.rerun()

    except Exception as e:
        st.error(f"Error reading file: {e}")
