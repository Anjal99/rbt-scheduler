"""
SQLite database for persistent storage of therapists, clients, assignments, and users.
"""

import sqlite3
import os
import secrets
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash


def _db_path():
    local_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    os.makedirs(local_dir, exist_ok=True)
    return os.path.join(local_dir, 'scheduler.db')


DB_PATH = _db_path()


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS therapists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            days_available TEXT DEFAULT 'Mon - Fri',
            hours_available TEXT DEFAULT '8am - 5pm',
            in_home TEXT DEFAULT 'No',
            preferred_max_hours REAL,
            forty_hour_eligible TEXT DEFAULT 'No',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            schedule_needed TEXT DEFAULT '',
            days TEXT DEFAULT 'Mon - Fri',
            in_home TEXT DEFAULT 'Clinic',
            travel_notes TEXT DEFAULT '',
            intensity TEXT DEFAULT 'Low',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            therapist_name TEXT NOT NULL,
            day TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            location TEXT DEFAULT 'Clinic',
            assignment_type TEXT DEFAULT 'Recurring',
            lock_type TEXT DEFAULT NULL,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT DEFAULT 'staff',
            is_active INTEGER DEFAULT 1,
            invite_token TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    # Add lock_type column if missing (migration for existing DBs)
    try:
        conn.execute("SELECT lock_type FROM assignments LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE assignments ADD COLUMN lock_type TEXT DEFAULT NULL")

    conn.commit()
    conn.close()

    # Create default admin if no users exist
    _ensure_default_admin()


# ── Therapist CRUD ──────────────────────────────────────────────────────────

def get_all_therapists() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, name, days_available, hours_available, in_home, "
        "preferred_max_hours, forty_hour_eligible, notes FROM therapists ORDER BY name",
        conn
    )
    conn.close()
    return df


def add_therapist(name, days_available='Mon - Fri', hours_available='8am - 5pm',
                  in_home='No', preferred_max_hours=None,
                  forty_hour_eligible='No', notes=''):
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


def update_therapist(therapist_id, **kwargs):
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


def delete_therapist(therapist_id):
    conn = get_connection()
    conn.execute("DELETE FROM therapists WHERE id = ?", (therapist_id,))
    conn.commit()
    conn.close()


def bulk_import_therapists(df: pd.DataFrame) -> int:
    conn = get_connection()
    existing = set(
        row[0] for row in conn.execute("SELECT name FROM therapists").fetchall()
    )
    added = 0

    def clean(val, default=''):
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


def therapist_count():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM therapists").fetchone()[0]
    conn.close()
    return count


# ── Client CRUD ─────────────────────────────────────────────────────────────

def get_all_clients() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, name, schedule_needed, days, in_home, travel_notes, intensity, notes "
        "FROM clients ORDER BY name",
        conn
    )
    conn.close()
    return df


def bulk_import_clients(df: pd.DataFrame) -> int:
    conn = get_connection()
    existing = set(
        row[0] for row in conn.execute("SELECT name FROM clients").fetchall()
    )
    added = 0

    def clean(val, default=''):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        s = str(val).strip()
        return default if s.lower() in ('nan', 'none', '') else s

    for _, row in df.iterrows():
        name = clean(row.get('Name', row.get('name', '')))
        if not name or name in existing:
            continue

        conn.execute(
            "INSERT INTO clients (name, schedule_needed, days, in_home, travel_notes, intensity, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                name,
                clean(row.get('Schedule Needed', row.get('schedule_needed', ''))),
                clean(row.get('Days', row.get('days', '')), 'Mon - Fri'),
                clean(row.get('In-Home', row.get('in_home', '')), 'Clinic'),
                clean(row.get('Travel notes', row.get('travel_notes', ''))),
                clean(row.get('Intensity', row.get('intensity', '')), 'Low'),
                clean(row.get('Notes', row.get('notes', ''))),
            )
        )
        existing.add(name)
        added += 1

    conn.commit()
    conn.close()
    return added


def delete_all_clients():
    conn = get_connection()
    conn.execute("DELETE FROM clients")
    conn.commit()
    conn.close()


def client_count():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    conn.close()
    return count


# ── Assignment CRUD ─────────────────────────────────────────────────────────

def get_all_assignments() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, client_name as Client, therapist_name as Therapist, day as Day, "
        "start_time as Start, end_time as End, location as Location, "
        "assignment_type as Type, lock_type as LockType, notes as Notes "
        "FROM assignments ORDER BY day, start_time",
        conn
    )
    conn.close()
    return df


def save_assignments(assignments_df: pd.DataFrame):
    """Replace unlocked assignments with new data. Locked assignments are preserved."""
    conn = get_connection()
    # Only delete unlocked assignments; locked ones stay in the DB
    try:
        conn.execute("DELETE FROM assignments WHERE lock_type IS NULL")
    except Exception:
        # Fallback if lock_type column doesn't exist yet
        conn.execute("DELETE FROM assignments")

    for _, row in assignments_df.iterrows():
        start_val = row.get('Start', '')
        end_val = row.get('End', '')
        # Convert time objects to strings if needed
        if hasattr(start_val, 'strftime'):
            start_val = start_val.strftime('%H:%M')
        if hasattr(end_val, 'strftime'):
            end_val = end_val.strftime('%H:%M')

        conn.execute(
            "INSERT INTO assignments (client_name, therapist_name, day, start_time, end_time, "
            "location, assignment_type, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(row.get('Client', '')),
                str(row.get('Therapist', '')),
                str(row.get('Day', '')),
                str(start_val),
                str(end_val),
                str(row.get('Location', 'Clinic')),
                str(row.get('Type', 'Recurring')),
                str(row.get('Notes', '')),
            )
        )

    conn.commit()
    conn.close()


def update_assignment(assignment_id, **kwargs):
    allowed = {'client_name', 'therapist_name', 'day', 'start_time', 'end_time',
               'location', 'assignment_type', 'lock_type', 'notes'}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ', '.join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [assignment_id]
    conn = get_connection()
    conn.execute(f"UPDATE assignments SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def add_assignment(client_name, therapist_name, day, start_time, end_time,
                   location='Clinic', assignment_type='Recurring', lock_type=None,
                   notes=''):
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO assignments (client_name, therapist_name, day, start_time, end_time, "
        "location, assignment_type, lock_type, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (client_name, therapist_name, day, start_time, end_time,
         location, assignment_type, lock_type, notes)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def get_locked_assignments() -> pd.DataFrame:
    """Return all assignments that have a lock_type set (hard or soft)."""
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, client_name as Client, therapist_name as Therapist, day as Day, "
        "start_time as Start, end_time as End, location as Location, "
        "assignment_type as Type, lock_type as LockType, notes as Notes "
        "FROM assignments WHERE lock_type IS NOT NULL ORDER BY day, start_time",
        conn
    )
    conn.close()
    return df


def get_assignment_by_id(assignment_id):
    """Return a single assignment as a dict, or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id, client_name, therapist_name, day, start_time, end_time, "
        "location, assignment_type, lock_type, notes FROM assignments WHERE id = ?",
        (assignment_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_assignment(assignment_id):
    conn = get_connection()
    conn.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))
    conn.commit()
    conn.close()


def delete_all_assignments():
    conn = get_connection()
    conn.execute("DELETE FROM assignments")
    conn.commit()
    conn.close()


def delete_all_therapists():
    conn = get_connection()
    conn.execute("DELETE FROM therapists")
    conn.commit()
    conn.close()


def reset_all():
    """Clear all data from all tables (except users)."""
    conn = get_connection()
    conn.execute("DELETE FROM assignments")
    conn.execute("DELETE FROM clients")
    conn.execute("DELETE FROM therapists")
    conn.commit()
    conn.close()


# ── User Auth ───────────────────────────────────────────────────────────────

def _ensure_default_admin():
    """Create a default admin account if no users exist. Requires ADMIN_PASSWORD env var."""
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        default_pw = os.environ.get('ADMIN_PASSWORD')
        admin_email = os.environ.get('ADMIN_EMAIL', 'admin@clinic.com')
        if not default_pw:
            print("WARNING: No ADMIN_PASSWORD env var set. Set it to create the initial admin account.")
            conn.close()
            return
        conn.execute(
            "INSERT INTO users (email, password_hash, name, role) VALUES (?, ?, ?, ?)",
            (admin_email, generate_password_hash(default_pw), 'Admin', 'admin')
        )
        conn.commit()
    conn.close()


def authenticate_user(email, password):
    """Check email/password. Returns user dict or None."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE email = ? AND is_active = 1", (email,)).fetchone()
    conn.close()
    if row and check_password_hash(row['password_hash'], password):
        return {'id': row['id'], 'email': row['email'], 'name': row['name'], 'role': row['role']}
    return None


def get_all_users():
    """Return all users (without password hashes)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, email, name, role, is_active, invite_token, created_at FROM users ORDER BY name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_by_id(user_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT id, email, name, role, is_active FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def create_user(email, name, role='staff', password=None):
    """Create a new user. Returns (user_id, temp_password)."""
    temp_pw = password or secrets.token_urlsafe(10)
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash, name, role, invite_token) VALUES (?, ?, ?, ?, ?)",
            (email, generate_password_hash(temp_pw), name, role, secrets.token_urlsafe(32))
        )
        conn.commit()
        new_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return None, 'Email already exists'
    conn.close()
    return new_id, temp_pw


def update_user_password(user_id, new_password):
    conn = get_connection()
    conn.execute(
        "UPDATE users SET password_hash = ?, invite_token = NULL WHERE id = ?",
        (generate_password_hash(new_password), user_id)
    )
    conn.commit()
    conn.close()


def delete_user(user_id):
    conn = get_connection()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def deactivate_user(user_id):
    conn = get_connection()
    conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


# Initialize on import
init_db()
