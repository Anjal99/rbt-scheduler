import math
from flask import Blueprint, request, jsonify
import pandas as pd
from server.utils.database import (
    get_all_therapists, add_therapist, update_therapist,
    delete_therapist, bulk_import_therapists, therapist_count
)

therapists_bp = Blueprint('therapists', __name__)


def _clean_records(records):
    """Replace NaN/inf with None for JSON serialization."""
    for rec in records:
        for k, v in rec.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                rec[k] = None
    return records


@therapists_bp.route('', methods=['GET'])
def list_therapists():
    df = get_all_therapists()
    return jsonify(_clean_records(df.to_dict('records')))


@therapists_bp.route('', methods=['POST'])
def create_therapist():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Name is required'}), 400
    new_id = add_therapist(
        name=data['name'],
        days_available=data.get('days_available', 'Mon - Fri'),
        hours_available=data.get('hours_available', '8am - 5pm'),
        in_home=data.get('in_home', 'No'),
        preferred_max_hours=data.get('preferred_max_hours'),
        forty_hour_eligible=data.get('forty_hour_eligible', 'No'),
        notes=data.get('notes', '')
    )
    return jsonify({'id': new_id, 'message': 'Therapist added'}), 201


@therapists_bp.route('/<int:therapist_id>', methods=['PUT'])
def edit_therapist(therapist_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    update_therapist(therapist_id, **data)
    return jsonify({'message': 'Therapist updated'})


@therapists_bp.route('/<int:therapist_id>', methods=['DELETE'])
def remove_therapist(therapist_id):
    delete_therapist(therapist_id)
    return jsonify({'message': 'Therapist deleted'})


@therapists_bp.route('/import', methods=['POST'])
def import_therapists():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'error': 'Must be an Excel file'}), 400

    df = pd.read_excel(file, sheet_name='Therapists')
    added = bulk_import_therapists(df)
    return jsonify({'added': added, 'total': therapist_count()})


@therapists_bp.route('/count', methods=['GET'])
def count():
    return jsonify({'count': therapist_count()})
