import json
from app import db
from app.models import Project, Drawing, Requirement, Annotation

def test_annotation_hit_polygon(client):
    app = client.application
    with app.app_context():
        p = Project(title='T', units='mm')
        db.session.add(p); db.session.commit()
        d = Drawing(project_id=p.id, filename='fake.pdf', original_name='fake.pdf', page_count=2)
        r = Requirement(project_id=p.id, title='R', symbol_key='position', tolerance_unit='mm', diameter_modifier_bool=True, datum_refs=['A'])
        db.session.add_all([d,r]); db.session.commit()
        a = Annotation(requirement_id=r.id, drawing_id=d.id, page_index=1, kind='polygon', coords_json={'points':[{'x':0.1,'y':0.1},{'x':0.3,'y':0.1},{'x':0.2,'y':0.3}]})
        db.session.add(a); db.session.commit()
        # Hit inside
        res = client.get(f'/api/annotations/hit?drawing_id={d.id}&page_index=1&x=0.2&y=0.2')
        assert res.json['hit'] is True and res.json['requirement_id'] == r.id
        # Miss outside
        res2 = client.get(f'/api/annotations/hit?drawing_id={d.id}&page_index=1&x=0.9&y=0.9')
        assert res2.json['hit'] is False
