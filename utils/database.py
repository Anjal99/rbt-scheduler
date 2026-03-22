"""
SQLite database for persistent therapist storage.

On Streamlit Cloud, the filesystem is ephemeral — the DB lives in a temp
directory and is rebuilt each session. Locally it persists in data/.
"""

import sqlite3
import os
import tempfile
import pandas as pd


def _db_path():
    """
    Returns the DB path. Uses data/ locally (persistent).
    On Streamlit Cloud, uses a temp directory (ephemeral but functional).
    """
    local_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    if os.access(local_dir, os.W_OK) or not os.path.exists(local_dir):
        os.makedirs(local_dir, exist_ok=True)
        return os.path.join(local_dir, 'therapists.db')
    # Fallback to temp dir (Streamlit Cloud)
    tmp = os.path.join(tempfile.gettempdir(), 'therapy_scheduler')
    os.makedirs(tmp, exist_ok=True)
    return os.path.join(tmp, 'therapists.db')


DB_PATH = _db_path()


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the therapists table if it doesn't exist."""
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS therapists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            days_available TEXT DEFAULT 'Mon - Fri',
            hours_available TEXT DEFAULT '8am - 5pm',
            in_home TEXT DEFAULT 'No',
            preferred_max_hours REAL,
            forty_hour_eligible TEXT DEFAULT 'No',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def get_all_therapists() -> pd.DataFrame:
    """Return all therapists as a DataFrame."""
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, name, days_available, hours_available, in_home, "
        "preferred_max_hours, forty_hour_eligible, notes FROM therapists ORDER BY name",
        conn
    )
    conn.close()
    return df


def add_therapist(name: str, days_available: str = 'Mon - Fri',
                  hours_available: str = '8am - 5pm', in_home: str = 'No',
                  preferred_max_hours: float = None,
                  forty_hour_eligible: str = 'No', notes: str = '') -> int:
    """Add a new therapist. Returns the new ID."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO therapists (name, days_available, hours_available, in_home, "
        "preferred_max_hours, forty_hour_eligible, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, days_available, hours_available, in_home, preferred_max_hours,
         forty_hour_eligible, notes)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def update_therapist(therapist_id: int, **kwargs):
    """Update therapist fields. Pass only the fields to update."""
    if not kwargs:
        return
    allowed = {'name', 'days_available', 'hours_available', 'in_home',
               'preferred_max_hours', 'forty_hour_eligible', 'notes'}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return

    set_clause = ', '.join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [therapist_id]

    conn = get_connection()
    conn.execute(
        f"UPDATE therapists SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        values
    )
    conn.commit()
    conn.close()


def delete_therapist(therapist_id: int):
    """Delete a therapist by ID."""
    conn = get_connection()
    conn.execute("DELETE FROM therapists WHERE id = ?", (therapist_id,))
    conn.commit()
    conn.close()


def bulk_import_therapists(df: pd.DataFrame) -> int:
    """
    Import therapists from a DataFrame (e.g., from Excel upload).
    Skips duplicates by name. Returns count of newly added.
    """
    conn = get_connection()
    existing = set(
        row[0] for row in conn.execute("SELECT name FROM therapists").fetchall()
    )
    added = 0

    def clean(val, default=''):
        """Convert NaN/None to empty string."""
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        s = str(val).strip()
        return default if s.lower() in ('nan', 'none', '') else s

    for _, row in df.iterrows():
        name = clean(row.get('Name', row.get('name', '')))
        if not name or name in existing:
            continue

        pref_max = row.get('preferred max hours', row.get('Preferred Max Hours', None))
        if pref_max is not None and (isinstance(pref_max, float) and pd.isna(pref_max)):
            pref_max = None

        conn.execute(
            "INSERT INTO therapists (name, days_available, hours_available, in_home, "
            "preferred_max_hours, forty_hour_eligible, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                name,
                clean(row.get('Days Available', row.get('days_available', '')), 'Mon - Fri'),
                clean(row.get('Hours Available', row.get('hours_available', '')), '8am - 5pm'),
                clean(row.get('In home (Yes/No)', row.get('In-Home', row.get('in_home', ''))), 'No'),
                pref_max,
                clean(row.get('40 hour eligible (Yes,No)', row.get('forty_hour_eligible', '')), 'No'),
                clean(row.get('Notes', row.get('notes', '')), ''),
            )
        )
        existing.add(name)
        added += 1

    conn.commit()
    conn.close()
    return added


def therapist_count() -> int:
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM therapists").fetchone()[0]
    conn.close()
    return count


# Initialize on import
init_db()
