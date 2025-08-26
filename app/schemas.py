from marshmallow import Schema, fields, validate, validates_schema, ValidationError

class RequirementSchema(Schema):
    title = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    feature_name = fields.Str(allow_none=True)
    description = fields.Str(allow_none=True)
    symbol_key = fields.Str(required=True, validate=validate.OneOf([
        'position','flatness','straightness','circularity','cylindricity',
        'perpendicularity','parallelism','angularity',
        'profile_line','profile_surface',
        'circular_runout','total_runout',
        'concentricity','symmetry'
    ]))
    tolerance_value = fields.Decimal(allow_none=True, as_string=True)
    tolerance_unit = fields.Str(allow_none=True, validate=validate.OneOf(['mm','in']))
    diameter_modifier_bool = fields.Boolean()
    material_condition = fields.Str(allow_none=True, validate=validate.OneOf(['RFS','MMC','LMC']))
    datum_refs = fields.List(fields.Str(), allow_none=True)
    zone_shape = fields.Str(allow_none=True, validate=validate.OneOf(['cylindrical','spherical','planar']))
    fcf_text = fields.Str(allow_none=True)
    notes = fields.Str(allow_none=True)

    @validates_schema
    def validate_position_datums(self, data, **kwargs):
        if data.get('symbol_key') == 'position':
            # Encourage datums for position
            if not data.get('datum_refs'):
                raise ValidationError('Position requires at least one datum reference (e.g., A|B|C).', 'datum_refs')

class AnnotationSchema(Schema):
    requirement_id = fields.Int(required=True)
    drawing_id = fields.Int(required=True)
    page_index = fields.Int(required=True)
    kind = fields.Str(required=True, validate=validate.OneOf(['box','polygon']))
    coords_json = fields.Dict(required=True)  # normalized coords
    label = fields.Str(allow_none=True, validate=validate.Length(max=100))
    color_hex = fields.Str(allow_none=True, validate=validate.Regexp(r'^#(?:[0-9a-fA-F]{3}){1,2}$'))
