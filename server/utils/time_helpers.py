"""
Time and day parsing utilities.
Handles the varied formats found in clinic scheduling Excel files.
"""

import re
from datetime import time

DAYS_ORDER = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
WEEKDAYS = DAYS_ORDER[:5]
DAYS_SET = set(DAYS_ORDER)


def parse_time(s: str) -> time:
    """Parse '9am', '3:30pm', '12pm', '2:00pm', '14:30' (24h), etc."""
    s = s.strip().lower().replace('.', '')
    # Try 24-hour format first (HH:MM from database)
    m24 = re.match(r'^(\d{1,2}):(\d{2})$', s)
    if m24:
        return time(int(m24.group(1)), int(m24.group(2)))
    # Then try am/pm format
    m = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', s)
    if not m:
        raise ValueError(f"Cannot parse time: '{s}'")
    hour = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    ampm = m.group(3)
    if ampm == 'pm' and hour != 12:
        hour += 12
    elif ampm == 'am' and hour == 12:
        hour = 0
    return time(hour, minute)


def format_time(t: time) -> str:
    """Format time as '9:00 AM'."""
    h = t.hour
    m = t.minute
    ampm = 'AM' if h < 12 else 'PM'
    h12 = h if h <= 12 else h - 12
    if h12 == 0:
        h12 = 12
    return f"{h12}:{m:02d} {ampm}"


def format_time_short(t: time) -> str:
    """Format time as '9am', '3:30pm'."""
    h = t.hour
    m = t.minute
    ampm = 'am' if h < 12 else 'pm'
    h12 = h if h <= 12 else h - 12
    if h12 == 0:
        h12 = 12
    if m == 0:
        return f"{h12}{ampm}"
    return f"{h12}:{m:02d}{ampm}"


def time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def minutes_to_time(m: int) -> time:
    m = max(0, min(m, 23 * 60 + 59))
    return time(m // 60, m % 60)


def normalize_day(d: str) -> str:
    d = d.strip().rstrip(',').rstrip('.').capitalize()
    mapping = {
        'Monday': 'Mon', 'Tuesday': 'Tue', 'Wednesday': 'Wed',
        'Thursday': 'Thu', 'Friday': 'Fri', 'Saturday': 'Sat', 'Sunday': 'Sun',
        'Mon': 'Mon', 'Tue': 'Tue', 'Wed': 'Wed', 'Thu': 'Thu',
        'Fri': 'Fri', 'Sat': 'Sat', 'Sun': 'Sun',
        'Tues': 'Tue', 'Weds': 'Wed', 'Thurs': 'Thu', 'Thur': 'Thu',
    }
    return mapping.get(d, d)


def expand_day_range(start_day: str, end_day: str) -> list:
    s = normalize_day(start_day)
    e = normalize_day(end_day)
    if s not in DAYS_SET or e not in DAYS_SET:
        return []
    si = DAYS_ORDER.index(s)
    ei = DAYS_ORDER.index(e)
    return DAYS_ORDER[si:ei + 1]


def parse_days_string(s: str) -> tuple:
    """Parse days string. Returns (list_of_days, flexible_count_or_None)."""
    if not s or str(s).strip() == '' or str(s).strip().lower() == 'none':
        return (list(WEEKDAYS), None)

    s = str(s).strip()

    flex_m = re.match(r'(\d+)\s*days?\s*\(?\s*flexible\s*\)?', s, re.IGNORECASE)
    if flex_m:
        return (list(WEEKDAYS), int(flex_m.group(1)))

    s = s.replace('/', ', ')

    range_m = re.match(r'^(\w+)\s*[-\u2013]\s*(\w+)\s*$', s.strip())
    if range_m:
        days = expand_day_range(range_m.group(1), range_m.group(2))
        if days:
            return (days, None)

    if ',' in s:
        parts = [normalize_day(p.strip()) for p in s.split(',') if p.strip()]
        valid = [p for p in parts if p in DAYS_SET]
        if valid:
            return (valid, None)

    parts = s.split()
    days = [normalize_day(p) for p in parts if normalize_day(p) in DAYS_SET]
    if days:
        return (days, None)

    return (list(WEEKDAYS), None)


def format_days_list(days: list) -> str:
    if not days:
        return ""
    days = sorted(set(days), key=lambda d: DAYS_ORDER.index(d) if d in DAYS_ORDER else 99)
    if days == WEEKDAYS:
        return "Mon-Fri"
    if days == DAYS_ORDER[:6]:
        return "Mon-Sat"
    indices = [DAYS_ORDER.index(d) for d in days if d in DAYS_ORDER]
    if not indices:
        return ", ".join(days)
    indices.sort()
    if len(indices) > 2 and indices == list(range(indices[0], indices[-1] + 1)):
        return f"{DAYS_ORDER[indices[0]]}-{DAYS_ORDER[indices[-1]]}"
    return ", ".join(days)
