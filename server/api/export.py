from flask import Blueprint, send_file
import pandas as pd
import io
from datetime import time
from server.utils.database import get_all_assignments
from server.utils.time_helpers import format_time, DAYS_ORDER

export_bp = Blueprint('export', __name__)


def _format_time_val(val):
    if isinstance(val, time):
        return format_time(val)
    if isinstance(val, str) and ':' in val:
        try:
            parts = val.split(':')
            t = time(int(parts[0]), int(parts[1]))
            return format_time(t)
        except (ValueError, IndexError):
            pass
    return str(val)


@export_bp.route('/excel', methods=['GET'])
def export_excel():
    df = get_all_assignments()
    if df.empty:
        return {'error': 'No schedule to export'}, 400

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Summary sheet
        summary = df.copy()
        summary['Start'] = summary['Start'].apply(_format_time_val)
        summary['End'] = summary['End'].apply(_format_time_val)
        summary.to_excel(writer, sheet_name='All Assignments', index=False)

        # Per-day sheets
        for day in DAYS_ORDER:
            day_df = df[df['Day'] == day].copy()
            if not day_df.empty:
                day_df['Start'] = day_df['Start'].apply(_format_time_val)
                day_df['End'] = day_df['End'].apply(_format_time_val)
                day_df.to_excel(writer, sheet_name=day, index=False)

    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='schedule.xlsx'
    )


@export_bp.route('/csv', methods=['GET'])
def export_csv():
    df = get_all_assignments()
    if df.empty:
        return {'error': 'No schedule to export'}, 400

    df['Start'] = df['Start'].apply(_format_time_val)
    df['End'] = df['End'].apply(_format_time_val)

    output = io.StringIO()
    df.to_csv(output, index=False, sep='\t')
    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='schedule.csv'
    )
