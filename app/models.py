from datetime import datetime
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy import Enum as SAEnum, Numeric
from . import db

# Fallback JSON type for non-SQLite (Postgres has JSON native)
try:
    from sqlalchemy import JSON
except Exception:  # pragma: no cover
    JSON = SQLITE_JSON

units_enum = SAEnum('mm', 'in', name='units_enum')
mc_enum = SAEnum('RFS', 'MMC', 'LMC', name='material_condition_enum')
zone_enum = SAEnum('cylindrical', 'spherical', 'planar', name='zone_shape_enum')
ann_kind_enum = SAEnum('box', 'polygon', name='annotation_kind_enum')

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    customer = db.Column(db.String(200), nullable=True)
    revision = db.Column(db.String(50), nullable=True)
    units = db.Column(units_enum, nullable=False, default='mm')
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    drawings = db.relationship('Drawing', backref='project', lazy=True, cascade='all, delete-orphan')
    requirements = db.relationship('Requirement', backref='project', lazy=True, cascade='all, delete-orphan')

class Drawing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)  # stored filename
    original_name = db.Column(db.String(255), nullable=False)
    page_count = db.Column(db.Integer, default=1, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    annotations = db.relationship('Annotation', backref='drawing', lazy=True, cascade='all, delete-orphan')

class Requirement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    feature_name = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)

    symbol_key = db.Column(db.String(50), nullable=False)  # e.g., 'position', 'flatness'
    tolerance_value = db.Column(Numeric(10, 4), nullable=True)
    tolerance_unit = db.Column(db.String(10), nullable=True)  # e.g., 'mm'
    diameter_modifier_bool = db.Column(db.Boolean, default=False, nullable=False)
    material_condition = db.Column(mc_enum, nullable=True)  # 'RFS','MMC','LMC', or None
    datum_refs = db.Column(JSON, nullable=True)  # ordered like ["A","B","C"]
    zone_shape = db.Column(zone_enum, nullable=True)

    fcf_text = db.Column(db.String(255), nullable=True)    # rendered like "⌀0.2 | M | A | B | C"
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    annotations = db.relationship('Annotation', backref='requirement', lazy=True, cascade='all, delete-orphan')

class Annotation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requirement_id = db.Column(db.Integer, db.ForeignKey('requirement.id', ondelete='CASCADE'), nullable=False)
    drawing_id = db.Column(db.Integer, db.ForeignKey('drawing.id', ondelete='CASCADE'), nullable=False)
    page_index = db.Column(db.Integer, nullable=False, default=0)  # zero-based
    kind = db.Column(ann_kind_enum, nullable=False, default='box')
    coords_json = db.Column(JSON, nullable=False)  # normalized coords in [0..1]
    label = db.Column(db.String(100), nullable=True)
    color_hex = db.Column(db.String(7), nullable=True, default='#ff0066')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
