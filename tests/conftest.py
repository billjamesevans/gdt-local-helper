import os, tempfile, pytest
from app import create_app, db
from app.models import Project, Requirement
from decimal import Decimal

@pytest.fixture()
def client():
    # Use a temporary SQLite DB for tests
    db_fd, db_path = tempfile.mkstemp()
    os.close(db_fd)
    os.environ['DATABASE_URL'] = 'sqlite:///' + db_path
    os.environ['UPLOAD_FOLDER'] = os.path.join(tempfile.gettempdir(), 'uploads_test')
    os.makedirs(os.environ['UPLOAD_FOLDER'], exist_ok=True)

    app = create_app()
    app.config['TESTING'] = True

    with app.app_context():
        from flask_migrate import upgrade
        upgrade()  # run migrations

    with app.test_client() as client:
        yield client

    # Cleanup
    try:
        os.remove(db_path)
    except Exception:
        pass
