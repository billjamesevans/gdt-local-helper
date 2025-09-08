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
    insights: List[Dict[str, Any]] = []

    def add(kind: str, title: str, detail: str, severity: str = 'info', req: Optional[Requirement] = None, code: Optional[str] = None):
        insights.append({
            'kind': kind,
            'title': title,
            'detail': detail,
            'severity': severity,
            'requirement_id': (req.id if req else None),
            'code': code,
        })

    # Bonus tolerance explainer for MMC/LMC
    for r in requirements:
        if r.material_condition in ('MMC','LMC') and r.tolerance_value is not None:
            cond = r.material_condition
            example = f"If actual size departs from {cond} by +0.1, available tolerance increases to {Decimal(r.tolerance_value) + Decimal('0.1')} (bonus)."
            add('bonus', f"Bonus tolerance at {cond}", example, 'tip', r, 'BONUS_TOL')

    # Datum completeness/order/diameter for position
    for r in requirements:
        if r.symbol_key == 'position':
            datums = r.datum_refs or []
            if len(datums) == 0:
                add('datum', 'Position without datum', 'Add at least one datum (e.g., A|B|C).', 'warning', r, 'POS_NO_DATUM')
            if datums and datums != sorted(datums):
                add('datum_order', 'Non-ordered datums', 'Order datums A→Z to reflect precedence.', 'tip', r, 'DATUM_ORDER')
            if r.diameter_modifier_bool is False:
                add('diameter', 'Position without ⌀', 'Holes typically use ⌀ for the position zone.', 'tip', r, 'POS_NO_DIAMETER')
            if r.tolerance_value is None:
                add('tolerance', 'Missing tolerance value', 'Position requires a tolerance value.', 'error', r, 'POS_NO_TOL')

    # Symbols that generally require a tolerance value
    tol_expected = {'perpendicularity','parallelism','angularity','profile_line','profile_surface','circular_runout','total_runout','cylindricity','circularity'}
    for r in requirements:
        if r.symbol_key in tol_expected and r.tolerance_value is None:
            add('tolerance', f"Missing tolerance for {r.symbol_key.replace('_',' ')}", 'Specify a non-zero tolerance value.', 'warning', r, 'MISS_TOL')

    # Over-specification: profile + form controls
    keys = [r.symbol_key for r in requirements]
    if 'profile_surface' in keys and any(k in keys for k in ['flatness','straightness','circularity','cylindricity']):
        add('over_spec', 'Possible over-specification', 'Profile may already control form; check if form controls are redundant.', 'tip', None, 'OVER_SPEC')

    # Legacy controls
    for r in requirements:
        if r.symbol_key in ('symmetry','concentricity'):
            alt = 'position/profile' if r.symbol_key == 'symmetry' else 'position (datum axis)'
            add('legacy', f"Legacy control: {r.symbol_key}", f"Consider modern alternative: {alt}.", 'warning', r, 'LEGACY')

    # Inadmissible datum usage on form-only controls
    for r in requirements:
        if r.symbol_key in ('flatness','straightness','circularity','cylindricity') and r.datum_refs:
            add('datum', 'Datum on form-only control', 'Form controls do not reference datums.', 'warning', r, 'FORM_WITH_DATUM')

    # Datum duplicates
    for r in requirements:
        if r.datum_refs and len(set(r.datum_refs)) != len(r.datum_refs):
            add('datum', 'Repeated datum in reference frame', 'Avoid repeating the same datum in DRF unless intentional.', 'tip', r, 'DATUM_REPEAT')

    # Units mismatch
    proj_units = project.units
    for r in requirements:
        if r.tolerance_unit and r.tolerance_unit != proj_units:
            add('units', 'Unit mismatch', f"Requirement in {r.tolerance_unit} but project is {proj_units}.", 'info', r, 'UNIT_MISMATCH')

    # Duplicate requirement titles (possible duplicates)
    seen: Dict[Tuple[str, str], int] = {}
    for r in requirements:
        key = (r.title.strip().lower(), r.symbol_key)
        seen[key] = seen.get(key, 0) + 1
    for (title, sym), count in seen.items():
        if count > 1:
            add('duplicate', 'Duplicate requirement titles', f"There are {count} '{title}' requirements with symbol {sym}.", 'tip', None, 'DUP_TITLES')

    # Zone shape sanity hints
    expected_zone = {
        'flatness': 'planar',
        'perpendicularity': 'planar',
        'parallelism': 'planar',
        'profile_surface': None,  # varies
        'circularity': None,
        'cylindricity': 'cylindrical',
    }
    for r in requirements:
        exp = expected_zone.get(r.symbol_key)
        if exp and r.zone_shape and r.zone_shape != exp:
            add('zone', 'Unusual zone shape', f"{r.symbol_key.replace('_',' ').title()} usually uses {exp} zone shape.", 'tip', r, 'ZONE_SHAPE')

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
