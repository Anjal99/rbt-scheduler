from flask import Blueprint, request, jsonify
from datetime import time
import pandas as pd
from server.utils.database import (
    get_all_therapists, get_all_clients, get_all_assignments,
    save_assignments, update_assignment, add_assignment,
    delete_assignment, delete_all_assignments, reset_all,
    get_locked_assignments, get_assignment_by_id
)
from server.utils.scheduler_engine import generate_schedule
from server.utils.validators import validate_schedule
from server.utils.time_helpers import parse_time, format_time_short

schedule_bp = Blueprint('schedule', __name__)


def _assignments_to_json(df):
    """Convert assignments DataFrame to JSON-serializable format."""
    records = []
    for _, row in df.iterrows():
        rec = dict(row)
        # Convert time objects to strings
        for key in ('Start', 'End'):
            val = rec.get(key)
            if isinstance(val, time):
                rec[key] = val.strftime('%H:%M')
        records.append(rec)
    return records


def _prepare_clients_df():
    """Get clients in the format the scheduler expects (with original column names)."""
    df = get_all_clients()
    if df.empty:
        return df
    rename_map = {
        'name': 'Name',
        'schedule_needed': 'Schedule Needed',
        'days': 'Days',
        'in_home': 'In-Home',
        'travel_notes': 'Travel notes',
        'intensity': 'Intensity',
        'notes': 'Notes',
    }
    return df.rename(columns=rename_map)


def _prepare_assignments_df():
    """Get assignments from DB with time objects for validation."""
    df = get_all_assignments()
    if df.empty:
        return df
    for col in ('Start', 'End'):
        df[col] = df[col].apply(lambda v: _str_to_time(v) if isinstance(v, str) else v)
    return df


def _str_to_time(s):
    """Convert HH:MM string to time object."""
    if not s or s == 'None':
        return None
    try:
        parts = s.split(':')
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        return None


@schedule_bp.route('', methods=['GET'])
def get_schedule():
    df = get_all_assignments()
    return jsonify(_assignments_to_json(df))


@schedule_bp.route('/generate', methods=['POST'])
def gen_schedule():
    therapists_df = get_all_therapists()
    clients_df = _prepare_clients_df()

    if therapists_df.empty:
        return jsonify({'error': 'No therapists loaded. Import therapists first.'}), 400
    if clients_df.empty:
        return jsonify({'error': 'No clients loaded. Upload clients first.'}), 400

    locked_df = get_locked_assignments()
    assignments_df, warnings, stats = generate_schedule(therapists_df, clients_df, locked_df)

    # Save to DB (preserves locked assignments, replaces unlocked ones)
    save_assignments(assignments_df)

    return jsonify({
        'assignments': _assignments_to_json(assignments_df),
        'warnings': warnings,
        'stats': stats,
    })


@schedule_bp.route('/validate', methods=['POST'])
def validate():
    assignments_df = _prepare_assignments_df()
    therapists_df = get_all_therapists()
    clients_df = _prepare_clients_df()

    flags = validate_schedule(assignments_df, therapists_df, clients_df)
    return jsonify({
        'flags': flags,
        'counts': {
            'errors': sum(1 for f in flags if f['severity'] == 'Error'),
            'critical': sum(1 for f in flags if f['severity'] == 'Critical'),
            'warnings': sum(1 for f in flags if f['severity'] == 'Warning'),
            'info': sum(1 for f in flags if f['severity'] == 'Info'),
        }
    })


@schedule_bp.route('/assignment', methods=['POST'])
def create_assignment():
    data = request.get_json()
    required = ['client_name', 'therapist_name', 'day', 'start_time', 'end_time']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    new_id = add_assignment(
        client_name=data['client_name'],
        therapist_name=data['therapist_name'],
        day=data['day'],
        start_time=data['start_time'],
        end_time=data['end_time'],
        location=data.get('location', 'Clinic'),
        assignment_type=data.get('assignment_type', 'Recurring'),
        notes=data.get('notes', '')
    )
    return jsonify({'id': new_id, 'message': 'Assignment added'}), 201


@schedule_bp.route('/assignment/<int:assignment_id>', methods=['PUT'])
def edit_assignment(assignment_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Block edits on hard-locked assignments (except changing lock_type itself)
    existing = get_assignment_by_id(assignment_id)
    if existing and existing.get('lock_type') == 'hard':
        non_lock_fields = {k: v for k, v in data.items() if k != 'lock_type'}
        if non_lock_fields:
            return jsonify({'error': 'This assignment is hard-locked. Unlock it first to make changes.'}), 403

    update_assignment(assignment_id, **data)
    return jsonify({'message': 'Assignment updated'})


@schedule_bp.route('/assignment/<int:assignment_id>/lock', methods=['PATCH'])
def set_assignment_lock(assignment_id):
    data = request.get_json()
    if not data or 'lock_type' not in data:
        return jsonify({'error': 'lock_type is required'}), 400
    lock_val = data['lock_type']
    if lock_val not in ('hard', 'soft', None):
        return jsonify({'error': 'lock_type must be "hard", "soft", or null'}), 400
    update_assignment(assignment_id, lock_type=lock_val)
    return jsonify({'message': 'Lock updated', 'lock_type': lock_val})


@schedule_bp.route('/assignment/<int:assignment_id>', methods=['DELETE'])
def remove_assignment(assignment_id):
    delete_assignment(assignment_id)
    return jsonify({'message': 'Assignment deleted'})


@schedule_bp.route('/stats', methods=['GET'])
def schedule_stats():
    df = get_all_assignments()
    if df.empty:
        return jsonify({
            'total_assignments': 0,
            'total_therapists': 0,
            'total_clients': 0,
            'total_hours': 0,
        })

    hours = 0
    for _, row in df.iterrows():
        s = _str_to_time(row['Start']) if isinstance(row['Start'], str) else row['Start']
        e = _str_to_time(row['End']) if isinstance(row['End'], str) else row['End']
        if s and e:
            from server.utils.time_helpers import time_to_minutes
            hours += (time_to_minutes(e) - time_to_minutes(s)) / 60.0

    return jsonify({
        'total_assignments': len(df),
        'total_therapists': df['Therapist'].nunique(),
        'total_clients': df['Client'].nunique(),
        'total_hours': round(hours, 1),
    })


@schedule_bp.route('/reset', methods=['POST'])
def reset_everything():
    reset_all()
    return jsonify({'message': 'All data cleared'})
