"""
Scheduling engine -- works with DataFrames.
Takes therapist and client DataFrames, returns assignment DataFrame.
"""

import re
import pandas as pd
from dataclasses import dataclass
from datetime import time
from typing import Optional

from server.utils.time_helpers import (
    parse_time, time_to_minutes, minutes_to_time, format_time_short,
    parse_days_string, format_days_list, normalize_day, DAYS_ORDER, WEEKDAYS, DAYS_SET
)

# -- Constants ----------------------------------------------------------------

SOFT_CAP = 30.0
HARD_CAP = 35.0
FORTY_CAP = 40.0
BREAK_MINUTES = 30
MAX_CHAIN_HOURS = 4.0
HIGH_INTENSITY_MAX = 3.0
LOW_INTENSITY_MAX = 4.0


# -- Data Structures ----------------------------------------------------------

@dataclass
class TimeBlock:
    start: time
    end: time

    def duration_minutes(self) -> int:
        return time_to_minutes(self.end) - time_to_minutes(self.start)

    def duration_hours(self) -> float:
        return self.duration_minutes() / 60.0

    def overlaps(self, other: 'TimeBlock') -> bool:
        return self.start < other.end and other.start < self.end

    def intersection(self, other: 'TimeBlock') -> Optional['TimeBlock']:
        if not self.overlaps(other):
            return None
        s = max(self.start, other.start)
        e = min(self.end, other.end)
        if s >= e:
            return None
        return TimeBlock(s, e)

    def __repr__(self):
        return f"{format_time_short(self.start)}-{format_time_short(self.end)}"


@dataclass
class Therapist:
    name: str
    days: list
    availability: dict
    in_home: bool
    preferred_max_hours: Optional[float]
    forty_hour_eligible: bool
    is_float: bool = False
    direct_target: Optional[float] = None
    direct_max: Optional[float] = None
    notes: str = ""
    flexible_days: Optional[int] = None


@dataclass
class Client:
    name: str
    schedule: dict
    days: list
    location: str
    location_by_day: dict
    intensity: str
    notes: str = ""


@dataclass
class Assignment:
    client: str
    therapist: str
    day: str
    start: time
    end: time
    location: str
    assignment_type: str
    notes: str = ""

    def duration_hours(self) -> float:
        return (time_to_minutes(self.end) - time_to_minutes(self.start)) / 60.0


# -- Parsing Helpers ----------------------------------------------------------

def _extract_days_and_time(seg: str, default_days: list) -> tuple:
    time_pattern = r'(\d{1,2}(?::\d{2})?\s*(?:am|pm)\s*[-\u2013]\s*\d{1,2}(?::\d{2})?\s*(?:am|pm))'
    m = re.search(time_pattern, seg, re.IGNORECASE)
    if not m:
        return (default_days, None)
    time_part = m.group(1)
    prefix = seg[:m.start()].strip()
    if not prefix:
        return (default_days, time_part)
    range_m = re.match(r'^(\w+)\s*[-\u2013]\s*(\w+)$', prefix.strip())
    if range_m:
        days = expand_day_range_local(range_m.group(1), range_m.group(2))
        if days:
            return (days, time_part)
    day_tokens = re.findall(r'[A-Za-z]+', prefix)
    days = [normalize_day(t) for t in day_tokens if normalize_day(t) in DAYS_SET]
    if days:
        return (days, time_part)
    return (default_days, time_part)


def expand_day_range_local(start_day, end_day):
    from server.utils.time_helpers import expand_day_range
    return expand_day_range(start_day, end_day)


def _parse_time_range(s: str) -> Optional[TimeBlock]:
    s = s.strip()
    parts = re.split(r'\s*[-\u2013]\s*', s)
    if len(parts) != 2:
        return None
    try:
        start = parse_time(parts[0])
        end = parse_time(parts[1])
        if time_to_minutes(start) >= time_to_minutes(end):
            if start.hour >= 12:
                start = time(start.hour - 12, start.minute)
        if time_to_minutes(start) < time_to_minutes(end):
            return TimeBlock(start, end)
    except ValueError:
        pass
    return None


def parse_hours_string(hours_str: str, available_days: list) -> dict:
    result = {d: [] for d in available_days}
    if not hours_str or str(hours_str).strip() in ('', 'None', 'nan'):
        default = TimeBlock(time(8, 0), time(20, 0))
        for d in available_days:
            result[d] = [default]
        return result
    for seg in re.split(r',\s*', str(hours_str).strip()):
        seg = seg.strip()
        if not seg:
            continue
        days_for_seg, time_part = _extract_days_and_time(seg, available_days)
        if time_part:
            block = _parse_time_range(time_part)
            if block:
                for d in days_for_seg:
                    if d in result:
                        result[d].append(block)
    return result


def parse_client_schedule(schedule_str: str, days: list) -> dict:
    result = {}
    if not schedule_str or str(schedule_str).strip() in ('', 'None', 'nan'):
        return result
    for seg in re.split(r',\s*', str(schedule_str).strip()):
        seg = seg.strip()
        if not seg:
            continue
        days_for_seg, time_part = _extract_days_and_time(seg, days)
        if time_part:
            block = _parse_time_range(time_part)
            if block:
                for d in days_for_seg:
                    result[d] = block
    return result


def parse_hybrid_notes(notes: str) -> dict:
    result = {}
    if not notes:
        return result
    m = re.search(r'[Hh]ybrid:?\s*(.*)', notes)
    if not m:
        return result
    for part in m.group(1).split(';'):
        part = part.strip()
        if not part:
            continue
        loc = "Home" if re.search(r'in[-\s]?home', part, re.IGNORECASE) else "Clinic"
        for day_tok in re.findall(r'[A-Za-z]+', re.sub(r'(in[-\s]?home|clinic)', '', part, flags=re.IGNORECASE)):
            nd = normalize_day(day_tok)
            if nd in DAYS_SET:
                result[nd] = loc
    return result


def parse_float_notes(notes: str) -> tuple:
    if not notes:
        return (False, None, None)
    if 'float' not in notes.lower() and 'lead' not in notes.lower():
        return (False, None, None)
    target = None
    max_h = None
    m = re.search(r'Direct\s*Target:\s*(\d+)', notes, re.IGNORECASE)
    if m:
        target = int(m.group(1))
    m = re.search(r'Direct\s*Max:\s*(\d+)', notes, re.IGNORECASE)
    if m:
        max_h = int(m.group(1))
    return (True, target, max_h)


# -- DataFrame to Internal Model ----------------------------------------------

def df_to_therapists(df: pd.DataFrame) -> list:
    therapists = []
    for _, row in df.iterrows():
        name = str(row.get('name', row.get('Name', ''))).strip()
        if not name or name in ('', 'nan', 'None'):
            continue

        days_str = str(row.get('days_available', row.get('Days Available', ''))).strip()
        hours_str = str(row.get('hours_available', row.get('Hours Available', ''))).strip()

        in_home_val = str(row.get('in_home', row.get('In home (Yes/No)', row.get('In-Home', 'No')))).strip().lower()
        in_home = in_home_val in ('yes', 'true', '1')

        pref_max = row.get('preferred_max_hours', row.get('preferred max hours', row.get('Preferred Max Hours', None)))
        if pd.notna(pref_max):
            try:
                pref_max = float(pref_max)
            except (ValueError, TypeError):
                pref_max = None
        else:
            pref_max = None

        forty_str = str(row.get('forty_hour_eligible', row.get('40 hour eligible (Yes,No)', row.get('40 Hour Eligible', 'No')))).strip().lower()
        forty_eligible = forty_str in ('yes', 'true', '1')

        notes = str(row.get('notes', row.get('Notes', ''))).strip()
        if notes in ('nan', 'None'):
            notes = ''

        days, flex = parse_days_string(days_str)
        availability = parse_hours_string(hours_str, days)

        has_avail = any(len(blocks) > 0 for blocks in availability.values())
        if not has_avail and days_str in ('', 'None', 'nan'):
            continue

        is_float, dt, dm = parse_float_notes(notes)

        therapists.append(Therapist(
            name=name, days=days, availability=availability,
            in_home=in_home, preferred_max_hours=pref_max,
            forty_hour_eligible=forty_eligible, is_float=is_float,
            direct_target=dt, direct_max=dm, notes=notes,
            flexible_days=flex
        ))
    return therapists


def df_to_clients(df: pd.DataFrame) -> list:
    clients = []
    for _, row in df.iterrows():
        name = str(row.get('Name', row.get('name', ''))).strip()
        if not name or name in ('', 'nan', 'None'):
            continue

        schedule_str = str(row.get('Schedule Needed', row.get('schedule_needed', ''))).strip()
        days_str = str(row.get('Days', row.get('days', ''))).strip()
        location_val = str(row.get('In-Home', row.get('in_home', row.get('Location', 'Clinic')))).strip()
        intensity = str(row.get('Intensity', row.get('intensity', 'Low'))).strip().capitalize()
        notes = str(row.get('Notes', row.get('notes', ''))).strip()
        if notes in ('nan', 'None'):
            notes = ''

        days, _ = parse_days_string(days_str)
        schedule = parse_client_schedule(schedule_str, days)

        if 'home' in location_val.lower() and 'hybrid' not in location_val.lower():
            location = 'Home'
        elif 'hybrid' in location_val.lower():
            location = 'Hybrid'
        else:
            location = 'Clinic'

        if location == 'Hybrid':
            location_by_day = parse_hybrid_notes(notes)
            for d in days:
                if d not in location_by_day:
                    location_by_day[d] = 'Clinic'
        elif location == 'Home':
            location_by_day = {d: 'Home' for d in days}
        else:
            location_by_day = {d: 'Clinic' for d in days}

        clients.append(Client(
            name=name, schedule=schedule, days=days,
            location=location, location_by_day=location_by_day,
            intensity=intensity, notes=notes
        ))
    return clients


# -- Scheduling Logic ----------------------------------------------------------

def time_add_minutes(t: time, mins: int) -> time:
    return minutes_to_time(time_to_minutes(t) + mins)


def therapist_weekly_hours(name: str, assignments: list) -> float:
    return sum(a.duration_hours() for a in assignments if a.therapist == name)


def therapist_day_assignments(name: str, day: str, assignments: list) -> list:
    result = [a for a in assignments if a.therapist == name and a.day == day]
    result.sort(key=lambda a: a.start)
    return result


def find_free_slots(therapist_name: str, day: str, timelines: dict,
                    assignments: list) -> list:
    blocks = timelines.get(therapist_name, {}).get(day, [])
    if not blocks:
        return []
    occupied = therapist_day_assignments(therapist_name, day, assignments)
    free = []
    for block in blocks:
        remaining = [TimeBlock(block.start, block.end)]
        for a in occupied:
            ablock = TimeBlock(a.start, a.end)
            new_remaining = []
            for r in remaining:
                if not r.overlaps(ablock):
                    new_remaining.append(r)
                else:
                    if r.start < ablock.start:
                        new_remaining.append(TimeBlock(r.start, ablock.start))
                    if r.end > ablock.end:
                        new_remaining.append(TimeBlock(ablock.end, r.end))
            remaining = new_remaining
        free.extend(r for r in remaining if r.duration_minutes() >= 15)
    return free


def chain_span_if_inserted(name: str, day: str, new_start: time, new_end: time,
                           assignments: list) -> float:
    day_a = therapist_day_assignments(name, day, assignments)
    new_s = time_to_minutes(new_start)
    new_e = time_to_minutes(new_end)
    chain_earliest = new_s
    chain_latest = new_e

    changed = True
    while changed:
        changed = False
        for a in day_a:
            a_s = time_to_minutes(a.start)
            a_e = time_to_minutes(a.end)
            gap = chain_earliest - a_e
            if -1 <= gap < BREAK_MINUTES and a_s < chain_earliest:
                chain_earliest = a_s
                changed = True

    changed = True
    while changed:
        changed = False
        for a in day_a:
            a_s = time_to_minutes(a.start)
            a_e = time_to_minutes(a.end)
            gap = a_s - chain_latest
            if -1 <= gap < BREAK_MINUTES and a_e > chain_latest:
                chain_latest = a_e
                changed = True

    return (chain_latest - chain_earliest) / 60.0


def travel_buffer_ok(name: str, day: str, new_start: time, new_end: time,
                     new_loc: str, assignments: list) -> bool:
    if new_loc != 'Home':
        return True
    for a in therapist_day_assignments(name, day, assignments):
        if a.location != 'Home':
            continue
        gap_after = time_to_minutes(new_start) - time_to_minutes(a.end)
        gap_before = time_to_minutes(a.start) - time_to_minutes(new_end)
        if 0 < gap_after < BREAK_MINUTES:
            return False
        if 0 < gap_before < BREAK_MINUTES:
            return False
    return True


def score_therapist(t: Therapist, client: Client, day: str,
                    overlap: TimeBlock, assignments: list,
                    soft_locked: list = None) -> float:
    score = 0.0
    weekly = therapist_weekly_hours(t.name, assignments)
    has_client = any(a.therapist == t.name and a.client == client.name for a in assignments)
    if has_client:
        score += 100
    has_client_today = any(
        a.therapist == t.name and a.client == client.name and a.day == day
        for a in assignments
    )
    if has_client_today:
        score += 50
    score += overlap.duration_hours() * 20
    score -= weekly * 1.0
    if t.is_float:
        score -= 60
    if t.preferred_max_hours and weekly >= t.preferred_max_hours:
        score -= 40
    if weekly >= HARD_CAP:
        score -= 200
    elif weekly >= HARD_CAP - 2:
        # Strong penalty when within 2h of hard cap to spread load
        score -= 150
    elif weekly >= SOFT_CAP:
        score -= 20
    # Soft lock bonus: strongly prefer keeping the same therapist-client-day combo
    if soft_locked:
        for sl in soft_locked:
            if sl.therapist == t.name and sl.client == client.name and sl.day == day:
                score += 200
                break
    return score


def try_assign_slot(client, day, remaining_start, remaining_end,
                    therapists, timelines, assignments, relaxed=False,
                    soft_locked=None):
    remaining_block = TimeBlock(remaining_start, remaining_end)
    day_loc = client.location_by_day.get(day, 'Clinic')
    intensity_max = HIGH_INTENSITY_MAX if client.intensity == 'High' else LOW_INTENSITY_MAX
    best_t = None
    best_overlap = None
    best_score = -9999

    for t in therapists:
        if day not in t.days:
            continue
        if day_loc == 'Home' and not t.in_home:
            continue
        weekly = therapist_weekly_hours(t.name, assignments)
        if t.is_float and t.direct_max and weekly >= t.direct_max:
            continue
        if not relaxed:
            # Normal mode: enforce 35h cap for everyone
            if weekly >= HARD_CAP:
                continue
        else:
            # Relaxed mode: allow 40h-eligible to go up to 40h, others stay at 35h
            if not t.forty_hour_eligible and weekly >= HARD_CAP:
                continue
            if t.forty_hour_eligible and weekly >= FORTY_CAP:
                continue

        free_slots = find_free_slots(t.name, day, timelines, assignments)
        for slot in free_slots:
            overlap = remaining_block.intersection(slot)
            if not overlap or overlap.duration_minutes() < 15:
                continue

            max_mins = int(intensity_max * 60)
            capped_mins = min(overlap.duration_minutes(), max_mins)
            capped_end = time_add_minutes(overlap.start, capped_mins)
            if time_to_minutes(capped_end) > time_to_minutes(overlap.end):
                capped_end = overlap.end

            while capped_mins >= 15:
                test_end = time_add_minutes(overlap.start, capped_mins)
                if time_to_minutes(test_end) > time_to_minutes(overlap.end):
                    test_end = overlap.end
                chain_span = chain_span_if_inserted(t.name, day, overlap.start, test_end, assignments)
                if chain_span <= MAX_CHAIN_HOURS + 0.01:
                    break
                capped_mins -= 15
            else:
                continue

            capped_end = time_add_minutes(overlap.start, capped_mins)
            if time_to_minutes(capped_end) > time_to_minutes(overlap.end):
                capped_end = overlap.end
            capped = TimeBlock(overlap.start, capped_end)
            if capped.duration_minutes() < 15:
                continue

            if not travel_buffer_ok(t.name, day, capped.start, capped.end, day_loc, assignments):
                continue

            # Projected hours check for single-day assignment
            cap_limit = FORTY_CAP if (relaxed and t.forty_hour_eligible) else HARD_CAP
            if weekly + capped.duration_hours() > cap_limit:
                max_mins = int((cap_limit - weekly) * 60)
                if max_mins < 15:
                    continue
                capped_mins_adj = min(capped.duration_minutes(), max_mins)
                capped_end_adj = time_add_minutes(capped.start, capped_mins_adj)
                if time_to_minutes(capped_end_adj) > time_to_minutes(capped.end):
                    capped_end_adj = capped.end
                capped = TimeBlock(capped.start, capped_end_adj)
                if capped.duration_minutes() < 15:
                    continue

            s = score_therapist(t, client, day, capped, assignments, soft_locked)
            if s > best_score:
                best_score = s
                best_t = t
                best_overlap = capped

    if best_t and best_overlap:
        atype = "Recurring"
        if best_t.is_float:
            rec_hours = sum(
                a.duration_hours() for a in assignments
                if a.therapist == best_t.name and a.assignment_type == "Recurring"
            )
            if best_t.direct_target and rec_hours >= best_t.direct_target:
                atype = "Float"

        return Assignment(
            client=client.name, therapist=best_t.name,
            day=day, start=best_overlap.start, end=best_overlap.end,
            location=day_loc, assignment_type=atype, notes=""
        )
    return None


# -- Main Entry Point ----------------------------------------------------------

def _find_common_free_slot(therapist, days, need_start, need_end, timelines, assignments):
    per_day_free = {}
    for d in days:
        per_day_free[d] = find_free_slots(therapist.name, d, timelines, assignments)

    candidates = [TimeBlock(need_start, need_end)]

    for d in days:
        day_free = per_day_free[d]
        new_candidates = []
        for cand in candidates:
            for slot in day_free:
                inter = cand.intersection(slot)
                if inter and inter.duration_minutes() >= 15:
                    new_candidates.append(inter)
        candidates = new_candidates
        if not candidates:
            return None

    if candidates:
        return max(candidates, key=lambda c: c.duration_minutes())
    return None


def try_assign_multi_day(client, days, remaining_start, remaining_end,
                         therapists, timelines, assignments, relaxed=False,
                         soft_locked=None):
    intensity_max = HIGH_INTENSITY_MAX if client.intensity == 'High' else LOW_INTENSITY_MAX
    best_t = None
    best_block = None
    best_score = -9999

    for t in therapists:
        if not all(d in t.days for d in days):
            continue

        day_loc = client.location_by_day.get(days[0], 'Clinic')
        if day_loc == 'Home' and not t.in_home:
            continue

        weekly = therapist_weekly_hours(t.name, assignments)
        if t.is_float and t.direct_max and weekly >= t.direct_max:
            continue
        if not relaxed:
            # Normal mode: enforce 35h cap for everyone
            if weekly >= HARD_CAP:
                continue
        else:
            # Relaxed mode: allow 40h-eligible to go up to 40h, others stay at 35h
            if not t.forty_hour_eligible and weekly >= HARD_CAP:
                continue
            if t.forty_hour_eligible and weekly >= FORTY_CAP:
                continue

        common = _find_common_free_slot(t, days, remaining_start, remaining_end,
                                         timelines, assignments)
        if not common or common.duration_minutes() < 15:
            continue

        max_mins = int(intensity_max * 60)
        capped_mins = min(common.duration_minutes(), max_mins)

        for d in days:
            test_end = time_add_minutes(common.start, capped_mins)
            if time_to_minutes(test_end) > time_to_minutes(common.end):
                test_end = common.end
            while capped_mins >= 15:
                test_end = time_add_minutes(common.start, capped_mins)
                if time_to_minutes(test_end) > time_to_minutes(common.end):
                    test_end = common.end
                chain = chain_span_if_inserted(t.name, d, common.start, test_end, assignments)
                if chain <= MAX_CHAIN_HOURS + 0.01:
                    break
                capped_mins -= 15
            if capped_mins < 15:
                break

        if capped_mins < 15:
            continue

        capped_end = time_add_minutes(common.start, capped_mins)
        if time_to_minutes(capped_end) > time_to_minutes(common.end):
            capped_end = common.end
        capped = TimeBlock(common.start, capped_end)

        # Projected hours check: block * num_days must not exceed cap
        added_hours = capped.duration_hours() * len(days)
        cap_limit = FORTY_CAP if (relaxed and t.forty_hour_eligible) else HARD_CAP
        if weekly + added_hours > cap_limit:
            # Shrink block to fit within cap
            max_per_day_mins = int((cap_limit - weekly) / len(days) * 60)
            if max_per_day_mins < 15:
                continue
            capped_mins = min(capped.duration_minutes(), max_per_day_mins)
            capped_end = time_add_minutes(common.start, capped_mins)
            if time_to_minutes(capped_end) > time_to_minutes(common.end):
                capped_end = common.end
            capped = TimeBlock(common.start, capped_end)
            if capped.duration_minutes() < 15:
                continue

        all_travel_ok = True
        for d in days:
            d_loc = client.location_by_day.get(d, 'Clinic')
            if not travel_buffer_ok(t.name, d, capped.start, capped.end, d_loc, assignments):
                all_travel_ok = False
                break
        if not all_travel_ok:
            continue

        s = score_therapist(t, client, days[0], capped, assignments, soft_locked)
        s += len(days) * 5

        if s > best_score:
            best_score = s
            best_t = t
            best_block = capped

    return best_t, best_block


def _locked_df_to_assignments(locked_df: pd.DataFrame) -> list:
    """Convert locked assignments DataFrame into Assignment objects."""
    assignments = []
    if locked_df is None or locked_df.empty:
        return assignments
    for _, row in locked_df.iterrows():
        start_val = row.get('Start', '')
        end_val = row.get('End', '')
        if isinstance(start_val, str):
            start_val = parse_time(start_val) if start_val else None
        if isinstance(end_val, str):
            end_val = parse_time(end_val) if end_val else None
        if not start_val or not end_val:
            continue
        assignments.append(Assignment(
            client=str(row.get('Client', '')),
            therapist=str(row.get('Therapist', '')),
            day=str(row.get('Day', '')),
            start=start_val,
            end=end_val,
            location=str(row.get('Location', 'Clinic')),
            assignment_type=str(row.get('Type', 'Recurring')),
            notes=str(row.get('Notes', '')),
        ))
    return assignments


def generate_schedule(therapists_df: pd.DataFrame,
                      clients_df: pd.DataFrame,
                      locked_df: pd.DataFrame = None) -> tuple:
    """
    Main entry point. Returns (assignments_df, warnings_list, stats_dict).
    Locked assignments (hard/soft) are pre-populated so the engine works around them.
    """
    therapists = df_to_therapists(therapists_df)
    clients = df_to_clients(clients_df)

    timelines = {}
    for t in therapists:
        day_blocks = {}
        for d in t.days:
            day_blocks[d] = list(t.availability.get(d, []))
        timelines[t.name] = day_blocks

    # Pre-populate with locked assignments so the engine routes around them
    locked_assignments = _locked_df_to_assignments(locked_df)
    # Build soft-locked list for scoring bonus
    soft_locked = []
    if locked_df is not None and not locked_df.empty:
        soft_rows = locked_df[locked_df['LockType'] == 'soft']
        soft_locked = _locked_df_to_assignments(soft_rows)
    assignments = list(locked_assignments)
    warnings = []

    def difficulty(c):
        total_hours = sum(tb.duration_hours() for tb in c.schedule.values())
        is_home = 1 if c.location in ('Home', 'Hybrid') else 0
        is_high = 1 if c.intensity == 'High' else 0
        return (-is_high, -is_home, -total_hours)

    sorted_clients = sorted(clients, key=difficulty)

    # -- Pass 1: Consistent multi-day scheduling --
    for client in sorted_clients:
        schedule_groups = {}
        for day in client.days:
            if day not in client.schedule:
                continue
            need = client.schedule[day]
            key = (time_to_minutes(need.start), time_to_minutes(need.end))
            if key not in schedule_groups:
                schedule_groups[key] = []
            schedule_groups[key].append(day)

        for (need_start_m, need_end_m), days in schedule_groups.items():
            need_start = minutes_to_time(need_start_m)
            need_end = minutes_to_time(need_end_m)
            remaining_start = need_start
            block_num = 1

            attempts = 0
            while time_to_minutes(remaining_start) < need_end_m:
                attempts += 1
                if attempts > 30:
                    break

                best_t, best_block = try_assign_multi_day(
                    client, days, remaining_start, need_end,
                    therapists, timelines, assignments,
                    soft_locked=soft_locked
                )
                if not best_t:
                    best_t, best_block = try_assign_multi_day(
                        client, days, remaining_start, need_end,
                        therapists, timelines, assignments, relaxed=True,
                        soft_locked=soft_locked
                    )

                if best_t and best_block:
                    for d in days:
                        d_loc = client.location_by_day.get(d, 'Clinic')
                        atype = "Recurring"
                        if best_t.is_float:
                            rec_hours = sum(
                                a.duration_hours() for a in assignments
                                if a.therapist == best_t.name and a.assignment_type == "Recurring"
                            )
                            if best_t.direct_target and rec_hours >= best_t.direct_target:
                                atype = "Float"

                        assignments.append(Assignment(
                            client=client.name, therapist=best_t.name,
                            day=d, start=best_block.start, end=best_block.end,
                            location=d_loc, assignment_type=atype,
                            notes=f"Block {block_num}"
                        ))

                    remaining_start = best_block.end
                    if time_to_minutes(remaining_start) < need_end_m:
                        block_num += 1
                else:
                    break

    # -- Pass 2: Fill gaps per-day --
    for client in sorted_clients:
        for day in client.days:
            if day not in client.schedule:
                continue
            need = client.schedule[day]
            day_a = sorted(
                [a for a in assignments if a.client == client.name and a.day == day],
                key=lambda a: a.start
            )
            gaps = []
            cursor = time_to_minutes(need.start)
            for a in day_a:
                a_start = time_to_minutes(a.start)
                if a_start > cursor:
                    gaps.append((minutes_to_time(cursor), a.start))
                cursor = max(cursor, time_to_minutes(a.end))
            if cursor < time_to_minutes(need.end):
                gaps.append((minutes_to_time(cursor), need.end))

            for gap_start, gap_end in gaps:
                remaining_start = gap_start
                block_num = len(day_a) + 1
                attempts = 0
                while time_to_minutes(remaining_start) < time_to_minutes(gap_end):
                    attempts += 1
                    if attempts > 15:
                        break
                    result = try_assign_slot(client, day, remaining_start, gap_end,
                                             therapists, timelines, assignments, relaxed=True,
                                             soft_locked=soft_locked)
                    if result:
                        result.notes = f"Block {block_num} (gap fill)"
                        assignments.append(result)
                        remaining_start = result.end
                        block_num += 1
                    else:
                        break

    # -- Collect warnings --
    for client in sorted_clients:
        for day in client.days:
            if day not in client.schedule:
                continue
            need = client.schedule[day]
            day_a = sorted(
                [a for a in assignments if a.client == client.name and a.day == day],
                key=lambda a: a.start
            )
            cursor = time_to_minutes(need.start)
            for a in day_a:
                if time_to_minutes(a.start) > cursor + 5:
                    warnings.append(
                        f"Coverage gap: {client.name} on {day} "
                        f"{format_time_short(minutes_to_time(cursor))}-{format_time_short(a.start)}"
                    )
                cursor = max(cursor, time_to_minutes(a.end))
            if cursor < time_to_minutes(need.end) - 5:
                warnings.append(
                    f"Coverage gap: {client.name} on {day} "
                    f"{format_time_short(minutes_to_time(cursor))}-{format_time_short(need.end)}"
                )

    for t in therapists:
        weekly = therapist_weekly_hours(t.name, assignments)
        if weekly < 0.01:
            continue
        if weekly >= FORTY_CAP and not t.forty_hour_eligible:
            warnings.append(f"CRITICAL: {t.name} at {weekly:.1f}h/week (NOT 40h eligible)")
        elif weekly >= FORTY_CAP:
            warnings.append(f"40h: {t.name} at {weekly:.1f}h/week -- verify 2h mid-day break")
        elif weekly >= HARD_CAP:
            warnings.append(f"High workload: {t.name} at {weekly:.1f}h/week (hard cap 35h)")
        elif weekly >= SOFT_CAP:
            warnings.append(f"Workload warning: {t.name} at {weekly:.1f}h/week (soft cap 30h)")
        if t.preferred_max_hours and weekly > t.preferred_max_hours:
            warnings.append(f"Over preferred max: {t.name} at {weekly:.1f}h (pref {t.preferred_max_hours}h)")

    total_needed = sum(tb.duration_hours() for c in clients for tb in c.schedule.values())
    total_assigned = sum(a.duration_hours() for a in assignments)

    stats = {
        'total_therapists': len(therapists),
        'total_clients': len(clients),
        'total_assignments': len(assignments),
        'total_hours_needed': total_needed,
        'total_hours_assigned': total_assigned,
        'coverage_pct': (total_assigned / total_needed * 100) if total_needed > 0 else 0,
        'warnings_count': len(warnings),
    }

    # Only output engine-generated assignments (not locked ones already in DB)
    num_locked = len(locked_assignments)
    new_assignments = assignments[num_locked:]

    rows = []
    for a in new_assignments:
        rows.append({
            'Client': a.client,
            'Therapist': a.therapist,
            'Day': a.day,
            'Start': a.start,
            'End': a.end,
            'Location': a.location,
            'Type': a.assignment_type,
            'Notes': a.notes,
        })

    assignments_df = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=['Client', 'Therapist', 'Day', 'Start', 'End', 'Location', 'Type', 'Notes']
    )

    return assignments_df, warnings, stats
