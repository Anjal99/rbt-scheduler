"""
Schedule Generation & Timetable View Page
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import time, datetime, timedelta
from io import BytesIO

from utils.database import get_all_therapists
from utils.scheduler_engine import generate_schedule
from utils.time_helpers import format_time, format_time_short, time_to_minutes, DAYS_ORDER
from utils.styles import apply_global_styles, sidebar_nav, page_header

st.set_page_config(page_title="Schedule", page_icon="📅", layout="wide")
apply_global_styles()
sidebar_nav()

page_header("Weekly Schedule", "Generate and view the optimized weekly timetable")

# ── Check prerequisites ──
therapists_df = get_all_therapists()
clients_df = st.session_state.get('clients_df', None)

if therapists_df.empty:
    st.warning("No therapists in the database. Add therapists first.")
    st.page_link("pages/1_therapists.py", label="Manage Therapists", icon="👥")
    st.stop()

if clients_df is None:
    st.warning("No client data loaded. Upload a patient list first.")
    st.page_link("pages/2_upload_clients.py", label="Upload Clients", icon="📄")
    st.stop()


# ── Generate ──
def run_schedule():
    with st.spinner("Generating schedule..."):
        adf, warnings, stats = generate_schedule(therapists_df, clients_df)
        st.session_state['assignments_df'] = adf
        st.session_state['schedule_warnings'] = warnings
        st.session_state['schedule_stats'] = stats
        st.session_state['schedule_generated'] = True


col_gen, col_regen = st.columns([3, 1])
with col_gen:
    if st.button("Generate Schedule", type="primary", use_container_width=True,
                  disabled=st.session_state.get('schedule_generated', False)):
        run_schedule()
        st.rerun()
with col_regen:
    if st.session_state.get('schedule_generated'):
        if st.button("Regenerate", use_container_width=True):
            run_schedule()
            st.rerun()

# Auto-generate on first visit
if not st.session_state.get('schedule_generated'):
    run_schedule()

if not st.session_state.get('schedule_generated'):
    st.stop()

assignments_df = st.session_state['assignments_df']
warnings = st.session_state['schedule_warnings']
stats = st.session_state['schedule_stats']

# ── Stats ──
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("Therapists", stats['total_therapists'])
with c2:
    st.metric("Clients", stats['total_clients'])
with c3:
    st.metric("Assignments", stats['total_assignments'])
with c4:
    st.metric("Hours", f"{stats['total_hours_assigned']:.0f}/{stats['total_hours_needed']:.0f}")
with c5:
    st.metric("Coverage", f"{stats['coverage_pct']:.0f}%")

if warnings:
    with st.expander(f"Warnings ({len(warnings)})", expanded=False):
        for w in warnings:
            if 'CRITICAL' in w:
                st.error(w)
            elif 'High workload' in w or '40h' in w:
                st.warning(w)
            else:
                st.info(w)

st.markdown("---")

# ── Views ──
view = st.radio(
    "View mode",
    ["Timetable", "Edit Schedule", "By Therapist", "By Client"],
    horizontal=True,
    label_visibility="collapsed"
)

# ── Color palette ──
COLORS = [
    '#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6',
    '#06B6D4', '#F43F5E', '#14B8A6', '#F97316', '#6366F1',
    '#EC4899', '#22D3EE', '#84CC16', '#A855F7', '#0EA5E9',
    '#E11D48', '#2DD4BF', '#FB923C', '#818CF8', '#34D399',
    '#FBBF24', '#38BDF8', '#4ADE80', '#FB7185', '#A78BFA',
    '#67E8F9', '#BEF264', '#C084FC', '#7DD3FC', '#86EFAC',
]

if view == "Timetable":
    day_tabs = st.tabs(DAYS_ORDER[:6])

    clients_list = sorted(assignments_df['Client'].unique()) if not assignments_df.empty else []
    color_map = {c: COLORS[i % len(COLORS)] for i, c in enumerate(clients_list)}

    for tab, day in zip(day_tabs, DAYS_ORDER[:6]):
        with tab:
            day_data = assignments_df[assignments_df['Day'] == day]
            if day_data.empty:
                st.info(f"No assignments on {day}")
                continue

            therapist_names = sorted(day_data['Therapist'].unique())

            fig = go.Figure()
            for _, row in day_data.iterrows():
                start_t = row['Start'] if isinstance(row['Start'], time) else time(8, 0)
                end_t = row['End'] if isinstance(row['End'], time) else time(17, 0)
                s_m = start_t.hour * 60 + start_t.minute
                e_m = end_t.hour * 60 + end_t.minute

                loc_icon = "🏠" if row['Location'] == 'Home' else ""

                fig.add_trace(go.Bar(
                    x=[e_m - s_m],
                    y=[row['Therapist']],
                    base=[s_m],
                    orientation='h',
                    marker=dict(
                        color=color_map.get(row['Client'], '#999'),
                        line=dict(color='white', width=1.5),
                    ),
                    text=f"{row['Client']} {loc_icon}",
                    textposition='inside',
                    textfont=dict(size=11, color='white', family='Arial'),
                    hovertemplate=(
                        f"<b>{row['Client']}</b><br>"
                        f"Therapist: {row['Therapist']}<br>"
                        f"Time: {format_time(start_t)} – {format_time(end_t)}<br>"
                        f"Location: {row['Location']}<br>"
                        f"Type: {row['Type']}<extra></extra>"
                    ),
                    showlegend=False,
                ))

            tick_hours = list(range(7, 21))
            tick_vals = [h * 60 for h in tick_hours]
            tick_text = [f"{h if h <= 12 else h - 12}{'am' if h < 12 else 'pm'}" for h in tick_hours]

            fig.update_layout(
                barmode='stack',
                height=max(350, len(therapist_names) * 32 + 80),
                xaxis=dict(
                    tickvals=tick_vals,
                    ticktext=tick_text,
                    range=[6.5 * 60, 20.5 * 60],
                    gridcolor='#E2E8F0',
                    gridwidth=0.5,
                    zeroline=False,
                ),
                yaxis=dict(
                    categoryorder='array',
                    categoryarray=list(reversed(therapist_names)),
                    tickfont=dict(size=12),
                ),
                margin=dict(l=10, r=10, t=10, b=30),
                plot_bgcolor='white',
                paper_bgcolor='white',
                bargap=0.3,
            )
            st.plotly_chart(fig, use_container_width=True)

    # Legend — wrapping flex layout for mobile
    legend_html = '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:0.5rem;">'
    for client in clients_list:
        c = color_map[client]
        legend_html += (
            f'<span style="background:{c};color:white;padding:3px 10px;'
            f'border-radius:6px;font-size:12px;font-weight:500;white-space:nowrap">{client}</span>'
        )
    legend_html += '</div>'
    st.markdown("**Clients:**")
    st.markdown(legend_html, unsafe_allow_html=True)

elif view == "Edit Schedule":
    from utils.validators import validate_schedule as run_validation

    # Build option lists
    all_therapist_names = sorted(therapists_df['name'].tolist())
    all_client_names = sorted(clients_df['Name'].tolist()) if 'Name' in clients_df.columns else sorted(clients_df['name'].tolist())
    day_options = DAYS_ORDER[:6]
    location_options = ["Clinic", "Home"]
    type_options = ["Recurring", "Float"]

    # Prepare editable copy
    edit_df = assignments_df.copy().reset_index(drop=True)

    # Sort for display
    day_order_map = {d: i for i, d in enumerate(DAYS_ORDER)}
    edit_df['_sort'] = edit_df['Day'].map(day_order_map).fillna(99)
    edit_df = edit_df.sort_values(['Client', '_sort', 'Start']).drop(columns=['_sort']).reset_index(drop=True)

    # Run validation on current state
    flags = run_validation(edit_df, therapists_df, clients_df)
    errors = [f for f in flags if f['severity'] in ('Error', 'Critical')]
    warns = [f for f in flags if f['severity'] == 'Warning']
    infos = [f for f in flags if f['severity'] == 'Info']

    if errors:
        st.error(f"{len(errors)} error(s) found")
    if warns:
        st.warning(f"{len(warns)} warning(s)")
    if not errors and not warns:
        st.success("No rule violations")

    if errors or warns:
        with st.expander(f"View {len(errors)} errors, {len(warns)} warnings"):
            for f in errors:
                st.error(f"**{f['rule']}** {f['who']} {f['day']}: {f['detail']}")
            for f in warns:
                st.warning(f"**{f['rule']}** {f['who']} {f['day']}: {f['detail']}")

    st.markdown("")

    # Editable table
    edited = st.data_editor(
        edit_df,
        use_container_width=True,
        height=500,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "Client": st.column_config.SelectboxColumn("Client", options=all_client_names, width="small"),
            "Therapist": st.column_config.SelectboxColumn("Therapist", options=all_therapist_names, width="medium"),
            "Day": st.column_config.SelectboxColumn("Day", options=day_options, width="small"),
            "Start": st.column_config.TimeColumn("Start", format="h:mm a", width="small"),
            "End": st.column_config.TimeColumn("End", format="h:mm a", width="small"),
            "Location": st.column_config.SelectboxColumn("Location", options=location_options, width="small"),
            "Type": st.column_config.SelectboxColumn("Type", options=type_options, width="small"),
            "Notes": st.column_config.TextColumn("Notes", width="medium"),
        },
        key="schedule_editor",
    )

    # Save button
    col_save, col_add = st.columns([1, 1])
    with col_save:
        if st.button("Save Changes", type="primary", use_container_width=True):
            # Validate before saving
            new_flags = run_validation(edited, therapists_df, clients_df)
            new_errors = [f for f in new_flags if f['severity'] in ('Error', 'Critical')]

            if new_errors:
                st.error(f"Cannot save: {len(new_errors)} error(s) remain. Fix overlaps and chain violations first.")
                for f in new_errors:
                    st.error(f"**{f['rule']}** {f['who']} {f['day']}: {f['detail']}")
            else:
                st.session_state['assignments_df'] = edited.copy()
                # Recalculate stats
                total_assigned = sum(
                    (time_to_minutes(r['End']) - time_to_minutes(r['Start'])) / 60.0
                    for _, r in edited.iterrows()
                    if isinstance(r['Start'], time) and isinstance(r['End'], time)
                )
                st.session_state['schedule_stats']['total_assignments'] = len(edited)
                st.session_state['schedule_stats']['total_hours_assigned'] = total_assigned
                needed = st.session_state['schedule_stats']['total_hours_needed']
                st.session_state['schedule_stats']['coverage_pct'] = (total_assigned / needed * 100) if needed > 0 else 0
                st.session_state['schedule_stats']['warnings_count'] = len(new_flags)
                st.success("Schedule saved!")
                st.rerun()

    # Quick-add form
    st.markdown("---")
    st.markdown("#### Add New Assignment")
    with st.form("add_assignment_form", clear_on_submit=True):
        ac1, ac2, ac3 = st.columns(3)
        with ac1:
            new_client = st.selectbox("Client", options=all_client_names, key="new_a_client")
            new_start = st.time_input("Start Time", value=time(8, 0), key="new_a_start")
        with ac2:
            new_therapist = st.selectbox("Therapist", options=all_therapist_names, key="new_a_therapist")
            new_end = st.time_input("End Time", value=time(12, 0), key="new_a_end")
        with ac3:
            new_day = st.selectbox("Day", options=day_options, key="new_a_day")
            new_loc = st.selectbox("Location", options=location_options, key="new_a_loc")

        if st.form_submit_button("Add Assignment", type="primary"):
            new_row = pd.DataFrame([{
                'Client': new_client,
                'Therapist': new_therapist,
                'Day': new_day,
                'Start': new_start,
                'End': new_end,
                'Location': new_loc,
                'Type': 'Recurring',
                'Notes': 'Manual',
            }])
            updated = pd.concat([st.session_state['assignments_df'], new_row], ignore_index=True)
            st.session_state['assignments_df'] = updated
            st.success(f"Added: {new_client} with {new_therapist} on {new_day} {format_time(new_start)}-{format_time(new_end)}")
            st.rerun()

elif view == "By Therapist":
    therapist_names = sorted(assignments_df['Therapist'].unique())
    selected = st.selectbox("Select Therapist", therapist_names)

    t_data = assignments_df[assignments_df['Therapist'] == selected]
    total_hrs = sum(
        (time_to_minutes(r['End']) - time_to_minutes(r['Start'])) / 60.0
        for _, r in t_data.iterrows()
        if isinstance(r['Start'], time) and isinstance(r['End'], time)
    )
    st.metric("Weekly Hours", f"{total_hrs:.1f}h")
    st.markdown("")

    day_order = {d: i for i, d in enumerate(DAYS_ORDER)}
    t_data = t_data.copy()
    t_data['_sort'] = t_data['Day'].map(day_order).fillna(99)
    t_data = t_data.sort_values(['_sort', 'Start'])

    for day in DAYS_ORDER:
        dd = t_data[t_data['Day'] == day]
        if dd.empty:
            continue
        st.markdown(f"**{day}**")
        for _, row in dd.iterrows():
            s = format_time(row['Start']) if isinstance(row['Start'], time) else str(row['Start'])
            e = format_time(row['End']) if isinstance(row['End'], time) else str(row['End'])
            icon = "🏠" if row['Location'] == 'Home' else "🏥"
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{s} – {e} &nbsp;|&nbsp; **{row['Client']}** &nbsp;{icon} {row['Location']} &nbsp;|&nbsp; {row['Type']}")

elif view == "By Client":
    client_names = sorted(assignments_df['Client'].unique())
    selected = st.selectbox("Select Client", client_names)

    c_data = assignments_df[assignments_df['Client'] == selected]
    total_hrs = sum(
        (time_to_minutes(r['End']) - time_to_minutes(r['Start'])) / 60.0
        for _, r in c_data.iterrows()
        if isinstance(r['Start'], time) and isinstance(r['End'], time)
    )
    st.metric("Weekly Hours", f"{total_hrs:.1f}h")
    st.markdown("")

    day_order = {d: i for i, d in enumerate(DAYS_ORDER)}
    c_data = c_data.copy()
    c_data['_sort'] = c_data['Day'].map(day_order).fillna(99)
    c_data = c_data.sort_values(['_sort', 'Start'])

    for day in DAYS_ORDER:
        dd = c_data[c_data['Day'] == day]
        if dd.empty:
            continue
        st.markdown(f"**{day}**")
        for _, row in dd.iterrows():
            s = format_time(row['Start']) if isinstance(row['Start'], time) else str(row['Start'])
            e = format_time(row['End']) if isinstance(row['End'], time) else str(row['End'])
            icon = "🏠" if row['Location'] == 'Home' else "🏥"
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{s} – {e} &nbsp;|&nbsp; **{row['Therapist']}** &nbsp;{icon} {row['Location']} &nbsp;|&nbsp; {row['Type']}")

st.markdown("---")

# ── Export ──
st.markdown("### Export")
col_e1, col_e2 = st.columns(2)

with col_e1:
    def make_excel():
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            exp = assignments_df.copy()
            exp['Start'] = exp['Start'].apply(lambda t: format_time(t) if isinstance(t, time) else str(t))
            exp['End'] = exp['End'].apply(lambda t: format_time(t) if isinstance(t, time) else str(t))
            day_order = {d: i for i, d in enumerate(DAYS_ORDER)}
            exp['_s'] = exp['Day'].map(day_order).fillna(99)
            exp = exp.sort_values(['Client', '_s', 'Start']).drop(columns=['_s'])
            exp.to_excel(writer, sheet_name='Schedule', index=False)

            for day in DAYS_ORDER[:6]:
                dd = assignments_df[assignments_df['Day'] == day].copy()
                if dd.empty:
                    continue
                dd['Start'] = dd['Start'].apply(lambda t: format_time(t) if isinstance(t, time) else str(t))
                dd['End'] = dd['End'].apply(lambda t: format_time(t) if isinstance(t, time) else str(t))
                dd.sort_values(['Therapist', 'Start']).to_excel(writer, sheet_name=day, index=False)
        return buf.getvalue()

    st.download_button(
        "Download Excel",
        data=make_excel(),
        file_name="weekly_schedule.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.ml.sheet",
        use_container_width=True,
        type="primary",
    )

with col_e2:
    def make_csv():
        exp = assignments_df.copy()
        exp['Start'] = exp['Start'].apply(lambda t: format_time_short(t) if isinstance(t, time) else str(t))
        exp['End'] = exp['End'].apply(lambda t: format_time_short(t) if isinstance(t, time) else str(t))
        day_order = {d: i for i, d in enumerate(DAYS_ORDER)}
        exp['_s'] = exp['Day'].map(day_order).fillna(99)
        exp = exp.sort_values(['Day', 'Therapist', 'Start']).drop(columns=['_s'])
        return exp.to_csv(index=False)

    st.download_button(
        "Download CSV",
        data=make_csv(),
        file_name="weekly_schedule.csv",
        mime="text/csv",
        use_container_width=True,
    )
