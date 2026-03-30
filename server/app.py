"""
Flask application factory with authentication.
"""

import os
from datetime import timedelta
from flask import Flask, session, request, jsonify
from flask_cors import CORS
from server.config import BASE_DIR


def create_app():
    app = Flask(__name__,
                static_folder=os.path.join(BASE_DIR, 'static'),
                static_url_path='')

    # Secret key for sessions — use env var in production
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        import warnings
        warnings.warn("SECRET_KEY not set! Using insecure default for development only.")
        secret_key = 'dev-only-not-for-production'
    app.secret_key = secret_key
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)

    # Only set secure cookies when not in debug mode (HTTPS in production)
    if not app.debug:
        app.config['SESSION_COOKIE_SECURE'] = True

    CORS(app, supports_credentials=True)

    # Register blueprints
    from server.api.auth import auth_bp
    from server.api.therapists import therapists_bp
    from server.api.clients import clients_bp
    from server.api.schedule import schedule_bp
    from server.api.export import export_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(therapists_bp, url_prefix='/api/therapists')
    app.register_blueprint(clients_bp, url_prefix='/api/clients')
    app.register_blueprint(schedule_bp, url_prefix='/api/schedule')
    app.register_blueprint(export_bp, url_prefix='/api/export')

    # ── Auth middleware: protect all routes except login and static ──
    PUBLIC_PATHS = {'/api/auth/login'}

    @app.before_request
    def require_auth():
        # Allow static files (CSS, JS, images)
        if request.path.startswith('/css/') or request.path.startswith('/js/'):
            return
        # Allow the login page and login API
        if request.path == '/login' or request.path in PUBLIC_PATHS:
            return
        # Allow the root page (it will redirect to login if not authed via JS)
        if request.path == '/' or request.path == '':
            return
        # All /api/ routes require auth
        if request.path.startswith('/api/'):
            if 'user_id' not in session:
                return jsonify({'error': 'Authentication required'}), 401

    @app.route('/')
    def index():
        return app.send_static_file('index.html')

    @app.route('/login')
    def login_page():
        return app.send_static_file('login.html')

    @app.errorhandler(404)
    def not_found(e):
        return {'error': 'Not found'}, 404

    @app.errorhandler(500)
    def server_error(e):
        return {'error': 'Internal server error'}, 500

    return app
