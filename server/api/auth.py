from flask import Blueprint, request, jsonify, session
from server.utils.database import (
    authenticate_user, get_all_users, get_user_by_id,
    create_user, update_user_password, delete_user, deactivate_user
)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password required'}), 400

    user = authenticate_user(data['email'], data['password'])
    if not user:
        return jsonify({'error': 'Invalid email or password'}), 401

    session['user_id'] = user['id']
    session['user_email'] = user['email']
    session['user_name'] = user['name']
    session['user_role'] = user['role']
    session.permanent = True

    return jsonify({'user': user, 'message': 'Logged in'})


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out'})


@auth_bp.route('/me', methods=['GET'])
def current_user():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    return jsonify({
        'id': session['user_id'],
        'email': session['user_email'],
        'name': session['user_name'],
        'role': session['user_role'],
    })


@auth_bp.route('/change-password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    data = request.get_json()
    if not data or not data.get('new_password'):
        return jsonify({'error': 'New password required'}), 400
    if len(data['new_password']) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    update_user_password(session['user_id'], data['new_password'])
    return jsonify({'message': 'Password updated'})


# ── Admin-only: User management ─────────────────────────────────────────────

@auth_bp.route('/users', methods=['GET'])
def list_users():
    if session.get('user_role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    return jsonify(get_all_users())


@auth_bp.route('/users', methods=['POST'])
def invite_user():
    if session.get('user_role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json()
    if not data or not data.get('email') or not data.get('name'):
        return jsonify({'error': 'Email and name required'}), 400

    role = data.get('role', 'staff')
    if role not in ('admin', 'staff'):
        return jsonify({'error': 'Role must be admin or staff'}), 400

    user_id, result = create_user(data['email'], data['name'], role)
    if user_id is None:
        return jsonify({'error': result}), 400

    return jsonify({
        'id': user_id,
        'temp_password': result,
        'message': f"User created. Temporary password: {result}"
    }), 201


@auth_bp.route('/users/<int:user_id>', methods=['DELETE'])
def remove_user(user_id):
    if session.get('user_role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    if user_id == session.get('user_id'):
        return jsonify({'error': 'Cannot delete yourself'}), 400
    delete_user(user_id)
    return jsonify({'message': 'User deleted'})


@auth_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
def reset_user_password(user_id):
    if session.get('user_role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    import secrets
    new_pw = secrets.token_urlsafe(10)
    update_user_password(user_id, new_pw)
    return jsonify({'temp_password': new_pw, 'message': f'Password reset. New temp password: {new_pw}'})
