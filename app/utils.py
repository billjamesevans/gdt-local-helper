import json
from decimal import Decimal
from typing import List, Tuple, Dict, Any, Optional

from flask import current_app
from .models import Requirement, Project
from math import isclose

def build_fcf_text(symbol_key: str, tolerance_value: Optional[Decimal], unit: Optional[str],
                   diameter: bool, material: Optional[str], datums: Optional[list]) -> str:
    parts = []
    sym_map = {
        'position': '⟂⦿',  # not precise glyph; for preview
        'flatness': '⌔',
        'straightness': '—',
        'circularity': '◯',
        'cylindricity': '◎',
        'perpendicularity': '⟂',
        'parallelism': '∥',
        'angularity': '∠',
        'profile_line': '∿',
        'profile_surface': '≈',
        'circular_runout': '↻',
        'total_runout': '⟲',
        'concentricity': '◎(legacy)',
        'symmetry': '≡(legacy)'
    }
    # Start with (approx) symbol visual
    parts.append(sym_map.get(symbol_key, symbol_key))
    # Tolerance block
    tol = ''
    if diameter:
        tol += '⌀'
    if tolerance_value is not None:
        tol += f"{tolerance_value}"
        if unit:
            tol += f" {unit}"
    if tol:
        parts.append(tol)
    # Material condition
    if material in ('MMC','LMC','RFS'):
        material_glyph = {'MMC':'Ⓜ','LMC':'Ⓛ','RFS':'Ⓢ'}.get(material, material)
        parts.append(material_glyph)
    # Datums
    if datums:
        parts.extend(datums)
    return ' | '.join(parts)

def explain_requirement(r: Requirement) -> str:
    # Plain-English explanation using known symbol semantics
    base = {
        'position': 'Controls the 3D location of the feature relative to the referenced datums.',
        'flatness': 'Controls the flatness of the surface without using any datums.',
        'profile_surface': 'Controls the 3D profile of a surface, relative to basic dimensions and optional datums.',
        'circular_runout': 'Controls composite form/orientation for each circular element during a single revolution.',
        'total_runout': 'Controls composite runout across the full surface length.',
        'perpendicularity': 'Controls the 90° orientation relative to the specified datum.',
        'concentricity': 'Legacy control; typically replace with position relative to a datum axis.',
        'symmetry': 'Legacy control; typically replace with position/profile.'
    }
    s = base.get(r.symbol_key, 'GD&T control.')
    extra = []
    if r.tolerance_value is not None:
        extra.append(f"Tolerance: {r.tolerance_value}{(' ' + r.tolerance_unit) if r.tolerance_unit else ''}." )
    if r.diameter_modifier_bool:
        extra.append('The zone is diametral (⌀).')
    if r.material_condition in ('MMC','LMC','RFS'):
        mc = {'MMC':'Max Material Condition', 'LMC':'Least Material Condition', 'RFS':'Regardless of Feature Size'}[r.material_condition]
        extra.append(f"Material condition: {mc}." )
    if r.datum_refs:
        extra.append('Datums: ' + ' | '.join(r.datum_refs) + '.')
    if r.zone_shape:
        extra.append(f"Zone shape: {r.zone_shape}." )
    if r.symbol_key in ('concentricity','symmetry'):
        extra.append('Note: ASME Y14.5-2018 discourages this in favor of position/profile due to inspection difficulty.')
    return ' '.join([s] + extra)

def compute_insights(project: Project, requirements: List[Requirement]) -> List[Dict[str, Any]]:
    insights = []
    # Bonus tolerance explainer for MMC/LMC
    for r in requirements:
        if r.material_condition in ('MMC','LMC') and r.tolerance_value is not None:
            cond = 'MMC' if r.material_condition == 'MMC' else 'LMC'
            example = f"If the actual size departs from {cond} by +0.1, the available tolerance increases to {Decimal(r.tolerance_value) + Decimal('0.1')} (bonus)."
            insights.append({
                'kind': 'bonus',
                'title': f"Bonus tolerance at {r.material_condition}",
                'detail': example,
                'requirement_id': r.id
            })
    # Datum completeness for position
    for r in requirements:
        if r.symbol_key == 'position':
            datums = r.datum_refs or []
            if len(datums) == 0:
                insights.append({'kind': 'datum', 'title': 'Position without datum', 'detail': 'Add at least one datum (e.g., A|B|C).', 'requirement_id': r.id})
            if datums != sorted(datums):
                insights.append({'kind': 'datum_order', 'title': 'Non-ordered datums', 'detail': 'Order datums A→Z to reflect precedence.', 'requirement_id': r.id})
            if r.diameter_modifier_bool is False:
                insights.append({'kind': 'diameter', 'title': 'Position without ⌀', 'detail': 'Holes typically use ⌀ for the position zone.', 'requirement_id': r.id})
    # Over-specification: form duplication under profile
    keys = [r.symbol_key for r in requirements]
    if 'profile_surface' in keys and any(k in keys for k in ['flatness','straightness','circularity','cylindricity']):
        insights.append({'kind': 'over_spec', 'title': 'Possible over-specification', 'detail': 'Profile may already control form; check if form controls are redundant.'})
    # Legacy controls
    for r in requirements:
        if r.symbol_key in ('symmetry','concentricity'):
            alt = 'position/profile' if r.symbol_key == 'symmetry' else 'position (datum axis)'
            insights.append({'kind': 'legacy', 'title': f"Legacy control: {r.symbol_key}", 'detail': f"Consider modern alternative: {alt}.", 'requirement_id': r.id})
    # Consistency checks
    # Units mismatch
    proj_units = project.units
    for r in requirements:
        if r.tolerance_unit and r.tolerance_unit != proj_units:
            insights.append({'kind': 'units', 'title': 'Unit mismatch', 'detail': f"Requirement in {r.tolerance_unit} but project is {proj_units}.", 'requirement_id': r.id})
    return insights

# Geometry helpers
def point_in_polygon(x: float, y: float, poly: List[Tuple[float, float]]) -> bool:
    # Ray casting algorithm
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i+1) % n]
        # Check edges; y between y1 and y2
        if ((y1 > y) != (y2 > y)):
            xinters = (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1
            if x < xinters:
                inside = not inside
    return inside

def hit_test(ann: Dict[str, Any], x: float, y: float) -> bool:
    # ann contains kind and coords_json (normalized)
    k = ann['kind']
    cj = ann['coords_json']
    if k == 'box':
        # coords_json: {x,y,w,h}
        return (x >= cj['x'] and x <= cj['x'] + cj['w'] and y >= cj['y'] and y <= cj['y'] + cj['h'])
    elif k == 'polygon':
        pts = cj.get('points', [])  # list of {'x':..., 'y':...}
        poly = [(p['x'], p['y']) for p in pts]
        return point_in_polygon(x, y, poly)
    return False
