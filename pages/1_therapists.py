"""
Therapists Management Page
"""

import streamlit as st
import pandas as pd
from utils.database import (
    get_all_therapists, add_therapist, update_therapist,
    delete_therapist, bulk_import_therapists, therapist_count
)
from utils.styles import apply_global_styles, sidebar_nav, page_header

st.set_page_config(page_title="Therapists", page_icon="👥", layout="wide")
apply_global_styles()
sidebar_nav()

page_header("Therapists", "Manage your therapist roster")

# ── Roster ──
df = get_all_therapists()

if not df.empty:
    # Stats row
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Therapists", len(df))
    with c2:
        in_home_count = len(df[df['in_home'].str.lower() == 'yes'])
        st.metric("In-Home Capable", in_home_count)
    with c3:
        forty_count = len(df[df['forty_hour_eligible'].str.lower() == 'yes'])
        st.metric("40h Eligible", forty_count)

    st.markdown("")

    # Editable table
    edited_df = st.data_editor(
        df.drop(columns=['id']),
        use_container_width=True,
        num_rows="fixed",
        hide_index=True,
        column_config={
            "name": st.column_config.TextColumn("Name", width="medium"),
            "days_available": st.column_config.TextColumn("Days", width="medium"),
            "hours_available": st.column_config.TextColumn("Hours", width="medium"),
            "in_home": st.column_config.SelectboxColumn("In-Home", options=["Yes", "No"], width="small"),
            "preferred_max_hours": st.column_config.NumberColumn("Pref Max", min_value=0, max_value=50, width="small"),
            "forty_hour_eligible": st.column_config.SelectboxColumn("40h", options=["Yes", "No"], width="small"),
            "notes": st.column_config.TextColumn("Notes", width="large"),
        },
        key="therapist_editor"
    )

    if st.button("Save Changes", type="primary"):
        for i, row in edited_df.iterrows():
            tid = df.iloc[i]['id']
            update_therapist(
                tid,
                name=row['name'],
                days_available=row['days_available'],
                hours_available=row['hours_available'],
                in_home=row['in_home'],
                preferred_max_hours=row['preferred_max_hours'],
                forty_hour_eligible=row['forty_hour_eligible'],
                notes=row['notes'] if pd.notna(row['notes']) else ''
            )
        st.success("Changes saved!")
        st.rerun()

st.markdown("---")

# ── Add / Import / Delete ──
tab_add, tab_import, tab_delete = st.tabs(["Add Therapist", "Import from Excel", "Remove Therapist"])

with tab_add:
    with st.form("add_therapist_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input("Name *", placeholder="e.g., Jane Smith")
            new_days = st.text_input("Days Available", value="Mon - Fri")
            new_hours = st.text_input("Hours Available", value="8am - 5pm")
        with col2:
            new_inhome = st.selectbox("In-Home Capable?", ["Yes", "No"])
            new_pref = st.number_input("Preferred Max Hours/Week", min_value=0.0,
                                       max_value=50.0, value=0.0, step=0.5,
                                       help="0 = no preference")
            new_forty = st.selectbox("40 Hour Eligible?", ["Yes", "No"])
        new_notes = st.text_input("Notes", placeholder="e.g., Role: Float/Lead; Direct Target: 20; Direct Max: 30")

        if st.form_submit_button("Add Therapist", type="primary"):
            if not new_name.strip():
                st.error("Name is required.")
            else:
                add_therapist(
                    name=new_name.strip(),
                    days_available=new_days,
                    hours_available=new_hours,
                    in_home=new_inhome,
                    preferred_max_hours=new_pref if new_pref > 0 else None,
                    forty_hour_eligible=new_forty,
                    notes=new_notes
                )
                st.success(f"Added {new_name.strip()}")
                st.rerun()

with tab_import:
    uploaded = st.file_uploader(
        "Upload an Excel file with a 'Therapists' sheet",
        type=["xlsx"],
        key="therapist_upload"
    )
    if uploaded:
        try:
            import_df = pd.read_excel(uploaded, sheet_name="Therapists")
            st.dataframe(import_df, use_container_width=True, height=200, hide_index=True)
            if st.button("Import These Therapists", type="primary"):
                count = bulk_import_therapists(import_df)
                if count > 0:
                    st.success(f"Imported {count} new therapist(s)!")
                    st.rerun()
                else:
                    st.info("No new therapists to import (all names already exist).")
        except Exception as e:
            st.error(f"Could not read file: {e}")

with tab_delete:
    if df.empty:
        st.info("No therapists to delete.")
    else:
        delete_name = st.selectbox("Select therapist to remove", options=df['name'].tolist())
        col_del, col_spacer = st.columns([1, 4])
        with col_del:
            if st.button("Remove Therapist", type="secondary"):
                tid = df[df['name'] == delete_name]['id'].values[0]
                delete_therapist(tid)
                st.success(f"Removed {delete_name}")
                st.rerun()
