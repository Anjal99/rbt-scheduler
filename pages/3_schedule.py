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
    ["Timetable", "Table", "By Therapist", "By Client"],
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

elif view == "Table":
    display_df = assignments_df.copy()
    display_df['Start'] = display_df['Start'].apply(
        lambda t: format_time(t) if isinstance(t, time) else str(t)
    )
    display_df['End'] = display_df['End'].apply(
        lambda t: format_time(t) if isinstance(t, time) else str(t)
    )
    day_order = {d: i for i, d in enumerate(DAYS_ORDER)}
    display_df['_sort'] = display_df['Day'].map(day_order).fillna(99)
    display_df = display_df.sort_values(['Client', '_sort', 'Start']).drop(columns=['_sort'])
    st.dataframe(display_df, use_container_width=True, height=600, hide_index=True)

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
