"""
Validation Dashboard
"""

import streamlit as st
import pandas as pd
from datetime import time

from utils.time_helpers import time_to_minutes, format_time, DAYS_ORDER
from utils.scheduler_engine import SOFT_CAP, HARD_CAP, FORTY_CAP, MAX_CHAIN_HOURS, BREAK_MINUTES
from utils.database import get_all_therapists
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


def run_validation(adf, tdf, cdf):
    flags = []

    # 1. Overlaps
    for therapist in adf['Therapist'].unique():
        for day in DAYS_ORDER:
            dd = adf[(adf['Therapist'] == therapist) & (adf['Day'] == day)].sort_values('Start')
            rows = dd.to_dict('records')
            for i in range(len(rows)):
                for j in range(i + 1, len(rows)):
                    s1 = rows[i]['Start'] if isinstance(rows[i]['Start'], time) else time(0)
                    e1 = rows[i]['End'] if isinstance(rows[i]['End'], time) else time(0)
                    s2 = rows[j]['Start'] if isinstance(rows[j]['Start'], time) else time(0)
                    e2 = rows[j]['End'] if isinstance(rows[j]['End'], time) else time(0)
                    if s1 < e2 and s2 < e1:
                        flags.append({
                            'severity': 'Error',
                            'rule': 'No Overlaps',
                            'who': therapist,
                            'day': day,
                            'detail': f"{rows[i]['Client']} ({format_time(s1)}-{format_time(e1)}) overlaps {rows[j]['Client']} ({format_time(s2)}-{format_time(e2)})"
                        })

    # 2. Chain violations
    for therapist in adf['Therapist'].unique():
        for day in DAYS_ORDER:
            dd = adf[(adf['Therapist'] == therapist) & (adf['Day'] == day)].sort_values('Start')
            if dd.empty:
                continue
            rows = dd.to_dict('records')
            cs = time_to_minutes(rows[0]['Start']) if isinstance(rows[0]['Start'], time) else 0
            ce = time_to_minutes(rows[0]['End']) if isinstance(rows[0]['End'], time) else 0

            for i in range(1, len(rows)):
                a_s = time_to_minutes(rows[i]['Start']) if isinstance(rows[i]['Start'], time) else 0
                a_e = time_to_minutes(rows[i]['End']) if isinstance(rows[i]['End'], time) else 0
                if a_s - ce < BREAK_MINUTES:
                    ce = a_e
                else:
                    hrs = (ce - cs) / 60.0
                    if hrs > MAX_CHAIN_HOURS + 0.01:
                        flags.append({
                            'severity': 'Error',
                            'rule': '4h Break Rule',
                            'who': therapist,
                            'day': day,
                            'detail': f"{hrs:.1f}h continuous without a 30-min break"
                        })
                    cs, ce = a_s, a_e

            hrs = (ce - cs) / 60.0
            if hrs > MAX_CHAIN_HOURS + 0.01:
                flags.append({
                    'severity': 'Error',
                    'rule': '4h Break Rule',
                    'who': therapist,
                    'day': day,
                    'detail': f"{hrs:.1f}h continuous without a 30-min break"
                })

    # 3. Workload
    for therapist in adf['Therapist'].unique():
        td = adf[adf['Therapist'] == therapist]
        weekly = sum(
            (time_to_minutes(r['End']) - time_to_minutes(r['Start'])) / 60.0
            for _, r in td.iterrows()
            if isinstance(r['Start'], time) and isinstance(r['End'], time)
        )
        t_info = tdf[tdf['name'] == therapist]
        forty_ok = False
        pref_max = None
        if not t_info.empty:
            forty_ok = str(t_info.iloc[0].get('forty_hour_eligible', 'No')).lower() in ('yes', 'true')
            pm = t_info.iloc[0].get('preferred_max_hours', None)
            if pd.notna(pm) and pm and float(pm) > 0:
                pref_max = float(pm)

        if weekly >= FORTY_CAP and not forty_ok:
            flags.append({'severity': 'Critical', 'rule': 'Workload', 'who': therapist, 'day': '', 'detail': f"{weekly:.1f}h — NOT 40h eligible"})
        elif weekly >= FORTY_CAP:
            flags.append({'severity': 'Warning', 'rule': '40h Rule', 'who': therapist, 'day': '', 'detail': f"{weekly:.1f}h — verify 2h mid-day break"})
        elif weekly >= HARD_CAP:
            flags.append({'severity': 'Warning', 'rule': 'Workload', 'who': therapist, 'day': '', 'detail': f"{weekly:.1f}h (hard cap {HARD_CAP}h)"})
        elif weekly >= SOFT_CAP:
            flags.append({'severity': 'Info', 'rule': 'Workload', 'who': therapist, 'day': '', 'detail': f"{weekly:.1f}h (soft cap {SOFT_CAP}h)"})
        if pref_max and weekly > pref_max:
            flags.append({'severity': 'Warning', 'rule': 'Pref Max', 'who': therapist, 'day': '', 'detail': f"{weekly:.1f}h exceeds preferred {pref_max}h"})

    # 4. Unscheduled clients
    if not cdf.empty:
        for _, crow in cdf.iterrows():
            cn = str(crow.get('Name', crow.get('name', ''))).strip()
            if cn and cn not in ('', 'nan') and adf[adf['Client'] == cn].empty:
                flags.append({'severity': 'Error', 'rule': 'Coverage', 'who': cn, 'day': '', 'detail': 'Client has no assignments'})

    return flags


flags = run_validation(assignments_df, therapists_df, clients_df)

# ── Summary ──
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
    # Show by severity
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
