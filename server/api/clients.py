import math
from flask import Blueprint, request, jsonify
import pandas as pd
from server.utils.database import (
    get_all_clients, bulk_import_clients, delete_all_clients, client_count,
    update_client, add_client, delete_client, get_client_by_id,
    client_assignment_count
)

clients_bp = Blueprint('clients', __name__)


def _clean_records(records):
    """Replace NaN/inf with None for JSON serialization."""
    for rec in records:
        for k, v in rec.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                rec[k] = None
    return records


@clients_bp.route('', methods=['GET'])
def list_clients():
    df = get_all_clients()
    return jsonify(_clean_records(df.to_dict('records')))


@clients_bp.route('', methods=['POST'])
def create_client():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Name is required'}), 400

    approved = data.get('approved_hours')
    if approved in ('', None):
        approved = None
    else:
        try:
            approved = float(approved)
        except (TypeError, ValueError):
            return jsonify({'error': 'Approved hours must be a number'}), 400

    try:
        new_id = add_client(
            name=data['name'].strip(),
            schedule_needed=data.get('schedule_needed', ''),
            days=data.get('days', 'Mon - Fri'),
            in_home=data.get('in_home', 'Clinic'),
            travel_notes=data.get('travel_notes', ''),
            intensity=data.get('intensity', 'Low'),
            approved_hours=approved,
            notes=data.get('notes', ''),
        )
    except Exception as e:
        msg = str(e)
        if 'UNIQUE' in msg.upper():
            return jsonify({'error': 'A client with this name already exists'}), 400
        return jsonify({'error': msg}), 400

    return jsonify({'id': new_id, 'message': 'Client added'}), 201


@clients_bp.route('/upload', methods=['POST'])
def upload_clients():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'error': 'Must be an Excel file'}), 400

    xls = pd.ExcelFile(file)
    if 'Clients' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='Clients')
    else:
        df = pd.read_excel(xls, sheet_name=0)

    # Clear existing and reimport
    delete_all_clients()
    added = bulk_import_clients(df)
    return jsonify({'added': added, 'total': client_count()})


@clients_bp.route('/<int:client_id>', methods=['PUT'])
def edit_client(client_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    # Disallow renaming via PUT — name is the FK used in assignments
    data.pop('name', None)
    if 'approved_hours' in data:
        ah = data['approved_hours']
        if ah in ('', None):
            data['approved_hours'] = None
        else:
            try:
                data['approved_hours'] = float(ah)
            except (TypeError, ValueError):
                return jsonify({'error': 'Approved hours must be a number'}), 400
    update_client(client_id, **data)
    return jsonify({'message': 'Client updated'})


@clients_bp.route('/<int:client_id>', methods=['DELETE'])
def remove_client(client_id):
    client = get_client_by_id(client_id)
    if not client:
        return jsonify({'error': 'Client not found'}), 404

    n = client_assignment_count(client['name'])
    if n > 0:
        return jsonify({
            'error': f'Cannot delete: client has {n} scheduled assignment{"s" if n != 1 else ""}. Remove them first.'
        }), 409

    delete_client(client_id)
    return jsonify({'message': 'Client deleted'})


@clients_bp.route('/count', methods=['GET'])
def count():
    return jsonify({'count': client_count()})
