from app import db
from app.models import Project, Requirement
from decimal import Decimal
from app.utils import compute_insights

def test_insights_flags_legacy_and_bonus(client):
    from app import create_app
    app = create_app()
    with app.app_context():
        p = Project(title='T', units='mm')
        db.session.add(p); db.session.commit()
        r1 = Requirement(project_id=p.id, title='Hole pos', symbol_key='position', tolerance_value=Decimal('0.2'), tolerance_unit='mm', diameter_modifier_bool=True, material_condition='MMC', datum_refs=['A','B','C'])
        r2 = Requirement(project_id=p.id, title='Legacy sym', symbol_key='symmetry', tolerance_value=Decimal('0.1'), tolerance_unit='mm', datum_refs=['A'])
        db.session.add_all([r1,r2]); db.session.commit()
        ins = compute_insights(p, [r1,r2])
        kinds = {i['kind'] for i in ins}
        assert 'bonus' in kinds
        assert 'legacy' in kinds
