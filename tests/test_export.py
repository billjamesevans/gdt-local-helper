from app import db, create_app
from app.models import Project, Requirement
from decimal import Decimal

def test_export_csv_row_count(client):
    app = create_app()
    with app.app_context():
        p = Project(title='T', units='mm')
        db.session.add(p); db.session.commit()
        for i in range(3):
            r = Requirement(project_id=p.id, title=f'R{i}', symbol_key='flatness', tolerance_value=Decimal('0.1'), tolerance_unit='mm')
            db.session.add(r)
        db.session.commit()
        rv = client.get(f'/export/csv?project={p.id}')
        data = rv.data.decode('utf-8').splitlines()
        assert len(data) == 1 + 3  # header + rows
