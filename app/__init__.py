from flask import Flask, render_template, g, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, generate_csrf
from dotenv import load_dotenv
import os
from .config import Settings


db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()


def create_app():
    # Load env before constructing app
    load_dotenv()

    app = Flask(__name__, instance_relative_config=True, static_folder='static', template_folder='templates')
    app.config.from_object(Settings())

    # Force a single DB URL for BOTH the app and Alembic so migrations & runtime hit the same file
    db_url = os.getenv('DATABASE_URL') or app.config.get('SQLALCHEMY_DATABASE_URI') or f"sqlite:///{os.path.join(app.instance_path, 'gdt_helper.db')}"
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # Also set env var so `flask db ...` (Alembic) can read the same URL if env is consulted
    os.environ['DATABASE_URL'] = db_url
    # Optional: log for quick visibility during local debug
    try:
        app.logger.info(f"SQLALCHEMY_DATABASE_URI -> {db_url}")
    except Exception:
        pass

    # Ensure instance & uploads directories, and make uploads absolute
    os.makedirs(app.instance_path, exist_ok=True)
    up = app.config.get('UPLOAD_FOLDER', 'uploads')
    if not os.path.isabs(up):
        up = os.path.abspath(os.path.join(app.root_path, '..', up))
        app.config['UPLOAD_FOLDER'] = up
    os.makedirs(up, exist_ok=True)

    # Init extensions
    db.init_app(app)

    # IMPORTANT: import models BEFORE migrate.init_app so Alembic sees metadata
    # (prevents empty/No-op migrations that lead to 'no such table: project')
    from . import models  # noqa: F401

    migrate.init_app(app, db, render_as_batch=True)  # render_as_batch: smooth SQLite schema changes
    # Conditionally enable CSRF based on config
    if app.config.get('WTF_CSRF_ENABLED', True):
        csrf.init_app(app)

        @app.context_processor
        def inject_csrf_token():
            return dict(csrf_token=generate_csrf)

        @app.after_request
        def set_csrf_cookie(response):
            try:
                token = generate_csrf()
                response.set_cookie('csrf_token', token, samesite='Lax')
            except Exception:
                pass
            return response
    else:
        # Provide a no-op csrf_token for templates if disabled
        @app.context_processor
        def inject_csrf_token_disabled():
            return dict(csrf_token=lambda: "")

    # Bind host warning
    app.config['HOST_WARNING'] = (os.getenv('FLASK_RUN_HOST', '127.0.0.1') != '127.0.0.1')

    # Register routes
    from .routes import bp as main_bp
    app.register_blueprint(main_bp)

    # CLI: seed
    from .seed import register_seed_cli
    register_seed_cli(app)

    # Context processor for sidebar projects
    from .models import Project

    @app.context_processor
    def inject_projects():
        try:
            projects = Project.query.order_by(Project.created_at.desc()).all()
        except Exception:
            projects = []
        return dict(all_projects=projects, host_warning=app.config.get('HOST_WARNING', False))

    return app
