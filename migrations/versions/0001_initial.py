"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2025-08-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    units_enum = sa.Enum('mm','in', name='units_enum')
    material_condition_enum = sa.Enum('RFS','MMC','LMC', name='material_condition_enum')
    zone_shape_enum = sa.Enum('cylindrical','spherical','planar', name='zone_shape_enum')
    annotation_kind_enum = sa.Enum('box','polygon', name='annotation_kind_enum')

    units_enum.create(op.get_bind(), checkfirst=True)
    material_condition_enum.create(op.get_bind(), checkfirst=True)
    zone_shape_enum.create(op.get_bind(), checkfirst=True)
    annotation_kind_enum.create(op.get_bind(), checkfirst=True)

    op.create_table('project',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('customer', sa.String(length=200), nullable=True),
        sa.Column('revision', sa.String(length=50), nullable=True),
        sa.Column('units', units_enum, nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('drawing',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('original_name', sa.String(length=255), nullable=False),
        sa.Column('page_count', sa.Integer(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('requirement',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('feature_name', sa.String(length=200), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('symbol_key', sa.String(length=50), nullable=False),
        sa.Column('tolerance_value', sa.Numeric(10,4), nullable=True),
        sa.Column('tolerance_unit', sa.String(length=10), nullable=True),
        sa.Column('diameter_modifier_bool', sa.Boolean(), nullable=False),
        sa.Column('material_condition', material_condition_enum, nullable=True),
        sa.Column('datum_refs', sa.JSON(), nullable=True),
        sa.Column('zone_shape', zone_shape_enum, nullable=True),
        sa.Column('fcf_text', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('annotation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('requirement_id', sa.Integer(), nullable=False),
        sa.Column('drawing_id', sa.Integer(), nullable=False),
        sa.Column('page_index', sa.Integer(), nullable=False),
        sa.Column('kind', annotation_kind_enum, nullable=False),
        sa.Column('coords_json', sa.JSON(), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=True),
        sa.Column('color_hex', sa.String(length=7), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['drawing_id'], ['drawing.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['requirement_id'], ['requirement.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('annotation')
    op.drop_table('requirement')
    op.drop_table('drawing')
    op.drop_table('project')
    sa.Enum(name='annotation_kind_enum').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='zone_shape_enum').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='material_condition_enum').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='units_enum').drop(op.get_bind(), checkfirst=True)
