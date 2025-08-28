import os, io
from decimal import Decimal
from flask import current_app
from flask.cli import with_appcontext
import click
from . import db
from .models import Project, Drawing, Requirement, Annotation
from .utils import build_fcf_text
from .scripts.demo_pdf import create_demo_pdf
from PyPDF2 import PdfReader

@click.command('seed')
@with_appcontext
def seed_command():
    # Clear existing?
    if Project.query.count() == 0:
        proj = Project(title='Demo Gearbox Bracket', customer='Acme Robotics', revision='A', units='mm',
                       notes='Seeded project with demo drawings and requirements.')
        db.session.add(proj)
        db.session.commit()

        # Create demo PDFs (2 drawings)
        for name in ['Bracket', 'Shaft']:
            filename = f"demo_{name.lower()}.pdf"
            path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            create_demo_pdf(path, title=f"{name} Drawing", pages=3)

            with open(path, 'rb') as f:
                reader = PdfReader(io.BytesIO(f.read()))
                page_count = len(reader.pages)

            drw = Drawing(project_id=proj.id, filename=filename, original_name=filename, page_count=page_count)
            db.session.add(drw)
            db.session.commit()

        # Add varied requirements
        def add_req(**kw):
            r = Requirement(project_id=proj.id, **kw)
            db.session.add(r)
            db.session.commit()
            return r

        r1 = add_req(
            title='Mounting hole pattern',
            feature_name='Ø6 bolt holes (4x)',
            description='Pattern relative to base datums.',
            symbol_key='position',
            tolerance_value=Decimal('0.2'),
            tolerance_unit='mm',
            diameter_modifier_bool=True,
            material_condition='MMC',
            datum_refs=['A','B','C'],
            zone_shape='cylindrical',
            fcf_text=build_fcf_text('position', Decimal('0.2'), 'mm', True, 'MMC', ['A','B','C'])
        )
        r2 = add_req(
            title='Mating face flatness',
            feature_name='Top pad',
            description='Pad must be flat for seal.',
            symbol_key='flatness',
            tolerance_value=Decimal('0.1'),
            tolerance_unit='mm',
            diameter_modifier_bool=False,
            datum_refs=None,
            zone_shape='planar',
            fcf_text=build_fcf_text('flatness', Decimal('0.1'), 'mm', False, None, None)
        )
        r3 = add_req(
            title='Shaft profile',
            feature_name='Freeform surface',
            description='Surface profile relative to A|B.',
            symbol_key='profile_surface',
            tolerance_value=Decimal('0.5'),
            tolerance_unit='mm',
            material_condition=None,
            datum_refs=['A','B'],
            zone_shape='cylindrical',
            fcf_text=build_fcf_text('profile_surface', Decimal('0.5'), 'mm', False, None, ['A','B'])
        )
        r4 = add_req(
            title='Bearing seat runout',
            feature_name='Ø20 seat',
            description='Runout relative to axis A.',
            symbol_key='circular_runout',
            tolerance_value=Decimal('0.02'),
            tolerance_unit='mm',
            datum_refs=['A'],
            zone_shape='cylindrical',
            fcf_text=build_fcf_text('circular_runout', Decimal('0.02'), 'mm', False, None, ['A'])
        )
        r5 = add_req(
            title='Total runout main journal',
            feature_name='Ø25 journal',
            description='Total runout to datum A.',
            symbol_key='total_runout',
            tolerance_value=Decimal('0.05'),
            tolerance_unit='mm',
            datum_refs=['A'],
            zone_shape='cylindrical',
            fcf_text=build_fcf_text('total_runout', Decimal('0.05'), 'mm', False, None, ['A'])
        )
        r6 = add_req(
            title='Perpendicular face',
            feature_name='Side wall',
            description='Must be square to A.',
            symbol_key='perpendicularity',
            tolerance_value=Decimal('0.1'),
            tolerance_unit='mm',
            datum_refs=['A'],
            zone_shape='planar',
            fcf_text=build_fcf_text('perpendicularity', Decimal('0.1'), 'mm', False, None, ['A'])
        )
        r7 = add_req(
            title='Legacy symmetry (for demo)',
            feature_name='Slot centerplane',
            description='Legacy control to be flagged.',
            symbol_key='symmetry',
            tolerance_value=Decimal('0.2'),
            tolerance_unit='mm',
            datum_refs=['A'],
            fcf_text=build_fcf_text('symmetry', Decimal('0.2'), 'mm', False, None, ['A'])
        )
        r8 = add_req(
            title='Legacy concentricity (for demo)',
            feature_name='Ø10 shaft',
            description='Legacy control to be flagged.',
            symbol_key='concentricity',
            tolerance_value=Decimal('0.1'),
            tolerance_unit='mm',
            datum_refs=['A'],
            fcf_text=build_fcf_text('concentricity', Decimal('0.1'), 'mm', False, None, ['A'])
        )

        # Simple sample annotations (normalized boxes on drawing 1 page 1)
        drw1 = Drawing.query.filter(Drawing.project_id==proj.id).order_by(Drawing.id.asc()).first()
        ann1 = Annotation(requirement_id=r1.id, drawing_id=drw1.id, page_index=0, kind='box',
                          coords_json={'x':0.15,'y':0.2,'w':0.2,'h':0.1}, label='Hole pattern', color_hex='#ff0066')
        ann2 = Annotation(requirement_id=r2.id, drawing_id=drw1.id, page_index=1, kind='polygon',
                          coords_json={'points':[{'x':0.6,'y':0.3},{'x':0.8,'y':0.35},{'x':0.75,'y':0.55}]},
                          label='Pad', color_hex='#0d6efd')
        db.session.add_all([ann1,ann2])
        db.session.commit()
    click.echo('Seed complete.')

def register_seed_cli(app):
    app.cli.add_command(seed_command)
