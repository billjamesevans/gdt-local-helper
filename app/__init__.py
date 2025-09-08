from flask import Flask, render_template, g, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
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

    # Ensure instance & uploads directories
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Init extensions
    db.init_app(app)
    migrate.init_app(
        app,
        db,
        render_as_batch=True,
        directory=os.path.abspath(os.path.join(app.root_path, "..", "migrations")),
    )  # render_as_batch: smooth SQLite schema changes
    csrf.init_app(app)

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
