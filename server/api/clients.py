from flask import Blueprint, request, jsonify
import pandas as pd
from server.utils.database import (
    get_all_clients, bulk_import_clients, delete_all_clients, client_count
)

clients_bp = Blueprint('clients', __name__)


@clients_bp.route('', methods=['GET'])
def list_clients():
    df = get_all_clients()
    df = df.where(pd.notna(df), None)
    return jsonify(df.to_dict('records'))


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


@clients_bp.route('/count', methods=['GET'])
def count():
    return jsonify({'count': client_count()})
