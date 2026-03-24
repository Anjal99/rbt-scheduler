"""
Real-time validation for schedule edits.
Checks individual assignments and full schedules against all rules.
"""

import pandas as pd
from datetime import time
from utils.time_helpers import time_to_minutes, format_time, DAYS_ORDER

BREAK_MINUTES = 30
MAX_CHAIN_HOURS = 4.0
SOFT_CAP = 30.0
HARD_CAP = 35.0
FORTY_CAP = 40.0


def _safe_time(val):
    """Convert a value to time, handling strings and None."""
    if isinstance(val, time):
        return val
    return None


def check_overlaps(assignments_df: pd.DataFrame) -> list:
    """Check for therapist double-bookings."""
    flags = []
    for therapist in assignments_df['Therapist'].unique():
        for day in DAYS_ORDER:
            dd = assignments_df[
                (assignments_df['Therapist'] == therapist) & (assignments_df['Day'] == day)
            ].sort_values('Start')
            rows = dd.to_dict('records')
            for i in range(len(rows)):
                for j in range(i + 1, len(rows)):
                    s1, e1 = _safe_time(rows[i]['Start']), _safe_time(rows[i]['End'])
                    s2, e2 = _safe_time(rows[j]['Start']), _safe_time(rows[j]['End'])
                    if not all([s1, e1, s2, e2]):
                        continue
                    if s1 < e2 and s2 < e1:
                        flags.append({
                            'severity': 'Error',
                            'rule': 'Overlap',
                            'who': therapist,
                            'day': day,
                            'detail': (
                                f"{rows[i]['Client']} ({format_time(s1)}-{format_time(e1)}) "
                                f"overlaps {rows[j]['Client']} ({format_time(s2)}-{format_time(e2)})"
                            ),
                        })
    return flags


def check_chains(assignments_df: pd.DataFrame) -> list:
    """Check for continuous chains exceeding 4h without a 30-min break."""
    flags = []
    for therapist in assignments_df['Therapist'].unique():
        for day in DAYS_ORDER:
            dd = assignments_df[
                (assignments_df['Therapist'] == therapist) & (assignments_df['Day'] == day)
            ].sort_values('Start')
            if dd.empty:
                continue
            rows = dd.to_dict('records')
            cs = time_to_minutes(rows[0]['Start']) if _safe_time(rows[0]['Start']) else 0
            ce = time_to_minutes(rows[0]['End']) if _safe_time(rows[0]['End']) else 0

            for i in range(1, len(rows)):
                a_s = time_to_minutes(rows[i]['Start']) if _safe_time(rows[i]['Start']) else 0
                a_e = time_to_minutes(rows[i]['End']) if _safe_time(rows[i]['End']) else 0
                if a_s - ce < BREAK_MINUTES:
                    ce = a_e
                else:
                    hrs = (ce - cs) / 60.0
                    if hrs > MAX_CHAIN_HOURS + 0.01:
                        flags.append({
                            'severity': 'Error',
                            'rule': '4h Break',
                            'who': therapist,
                            'day': day,
                            'detail': f"{hrs:.1f}h continuous without 30-min break",
                        })
                    cs, ce = a_s, a_e

            hrs = (ce - cs) / 60.0
            if hrs > MAX_CHAIN_HOURS + 0.01:
                flags.append({
                    'severity': 'Error',
                    'rule': '4h Break',
                    'who': therapist,
                    'day': day,
                    'detail': f"{hrs:.1f}h continuous without 30-min break",
                })
    return flags


def check_workloads(assignments_df: pd.DataFrame, therapists_df: pd.DataFrame = None) -> list:
    """Check therapist weekly workload against caps."""
    flags = []
    for therapist in assignments_df['Therapist'].unique():
        td = assignments_df[assignments_df['Therapist'] == therapist]
        weekly = sum(
            (time_to_minutes(r['End']) - time_to_minutes(r['Start'])) / 60.0
            for _, r in td.iterrows()
            if _safe_time(r['Start']) and _safe_time(r['End'])
        )

        forty_ok = False
        pref_max = None
        if therapists_df is not None and not therapists_df.empty:
            t_info = therapists_df[therapists_df['name'] == therapist]
            if not t_info.empty:
                forty_ok = str(t_info.iloc[0].get('forty_hour_eligible', 'No')).lower() in ('yes', 'true')
                pm = t_info.iloc[0].get('preferred_max_hours', None)
                if pd.notna(pm) and pm and float(pm) > 0:
                    pref_max = float(pm)

        if weekly >= FORTY_CAP and not forty_ok:
            flags.append({'severity': 'Critical', 'rule': 'Workload', 'who': therapist, 'day': '', 'detail': f"{weekly:.1f}h — NOT 40h eligible"})
        elif weekly >= FORTY_CAP:
            flags.append({'severity': 'Warning', 'rule': '40h', 'who': therapist, 'day': '', 'detail': f"{weekly:.1f}h — verify 2h mid-day break"})
        elif weekly >= HARD_CAP:
            flags.append({'severity': 'Warning', 'rule': 'Workload', 'who': therapist, 'day': '', 'detail': f"{weekly:.1f}h (hard cap {HARD_CAP}h)"})
        elif weekly >= SOFT_CAP:
            flags.append({'severity': 'Info', 'rule': 'Workload', 'who': therapist, 'day': '', 'detail': f"{weekly:.1f}h (soft cap {SOFT_CAP}h)"})

        if pref_max and weekly > pref_max:
            flags.append({'severity': 'Warning', 'rule': 'Pref Max', 'who': therapist, 'day': '', 'detail': f"{weekly:.1f}h exceeds preferred {pref_max}h"})

    return flags


def validate_schedule(assignments_df: pd.DataFrame,
                      therapists_df: pd.DataFrame = None,
                      clients_df: pd.DataFrame = None) -> list:
    """Run all validation checks. Returns list of flag dicts."""
    if assignments_df.empty:
        return []

    flags = []
    flags.extend(check_overlaps(assignments_df))
    flags.extend(check_chains(assignments_df))
    flags.extend(check_workloads(assignments_df, therapists_df))

    # Coverage check
    if clients_df is not None and not clients_df.empty:
        for _, crow in clients_df.iterrows():
            cn = str(crow.get('Name', crow.get('name', ''))).strip()
            if cn and cn not in ('', 'nan') and assignments_df[assignments_df['Client'] == cn].empty:
                flags.append({
                    'severity': 'Error',
                    'rule': 'Coverage',
                    'who': cn,
                    'day': '',
                    'detail': 'Client has no assignments',
                })

    return flags
