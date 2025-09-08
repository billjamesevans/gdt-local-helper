import os, io, json, uuid
from decimal import Decimal, InvalidOperation
from datetime import datetime
from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, send_file, abort, jsonify
from werkzeug.utils import safe_join
from markupsafe import Markup
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from sqlalchemy import or_, func

from . import db, csrf
from .models import Project, Drawing, Requirement, Annotation
from .schemas import RequirementSchema, AnnotationSchema
from .utils import build_fcf_text, explain_requirement, compute_insights, hit_test

bp = Blueprint('main', __name__)

ALLOWED_EXTS = {'.pdf'}

# -------------- Helpers --------------
def allowed_file(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTS

def pdf_magic_is_valid(stream: io.BytesIO) -> bool:
    head = stream.read(5)
    stream.seek(0)
    try:
        return head.startswith(b'%PDF')
    except Exception:
        return False

# Simple rate limiter (per-process, single-user)
_upload_timestamps = []
def check_upload_rate_limit():
    import time
    now = time.time()
    window = 60.0
    limit = 20  # 20 uploads/minute is generous for local use
    # Remove old entries
    while _upload_timestamps and now - _upload_timestamps[0] > window:
        _upload_timestamps.pop(0)
    if len(_upload_timestamps) >= limit:
        return False
    _upload_timestamps.append(now)
    return True

# -------------- Dashboard --------------
@bp.route('/')
def index():
    # Enhanced dashboard: search, totals, per-project counts, recent activity
    try:
        q = request.args.get('q', '').strip()
        base = Project.query
        if q:
            like = f"%{q}%"
            base = base.filter(
                or_(Project.title.ilike(like), Project.customer.ilike(like), Project.notes.ilike(like))
            )
        projects = base.order_by(Project.updated_at.desc()).all()

        totals = {
            'projects': db.session.query(func.count(Project.id)).scalar() or 0,
            'drawings': db.session.query(func.count(Drawing.id)).scalar() or 0,
            'requirements': db.session.query(func.count(Requirement.id)).scalar() or 0,
            'annotations': db.session.query(func.count(Annotation.id)).scalar() or 0,
        }

        ids = [p.id for p in projects]
        draw_counts, req_counts = {}, {}
        if ids:
            for pid, c in db.session.query(Drawing.project_id, func.count(Drawing.id))\
                                   .filter(Drawing.project_id.in_(ids))\
                                   .group_by(Drawing.project_id):
                draw_counts[pid] = c
            for pid, c in db.session.query(Requirement.project_id, func.count(Requirement.id))\
                                   .filter(Requirement.project_id.in_(ids))\
                                   .group_by(Requirement.project_id):
                req_counts[pid] = c

        recent_drawings = Drawing.query.order_by(Drawing.uploaded_at.desc()).limit(5).all()
        recent_requirements = Requirement.query.order_by(Requirement.created_at.desc()).limit(5).all()
    except Exception:
        projects = []
        totals = {'projects': 0, 'drawings': 0, 'requirements': 0, 'annotations': 0}
        draw_counts, req_counts = {}, {}
        recent_drawings, recent_requirements = [], []
        q = ''

    return render_template(
        'dashboard.html',
        projects=projects,
        totals=totals,
        draw_counts=draw_counts,
        req_counts=req_counts,
        recent_drawings=recent_drawings,
        recent_requirements=recent_requirements,
        q=q,
    )

# -------------- Projects --------------
@bp.route('/projects/new', methods=['GET','POST'])
def project_new():
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        if not title:
            flash('Title is required.', 'danger')
            return redirect(url_for('main.project_new'))
        project = Project(
            title=title,
            customer=request.form.get('customer'),
            revision=request.form.get('revision'),
            units=request.form.get('units') or 'mm',
            notes=request.form.get('notes')
        )
        db.session.add(project)
        db.session.commit()
        flash('Project created.', 'success')
        return redirect(url_for('main.project_detail', id=project.id))
    return render_template('project_edit.html', project=None)

@bp.route('/projects/<int:id>')
def project_detail(id):
    project = Project.query.get_or_404(id)
    drawings = Drawing.query.filter_by(project_id=id).order_by(Drawing.uploaded_at.desc()).all()
    requirements = Requirement.query.filter_by(project_id=id).order_by(Requirement.created_at.desc()).all()
    return render_template('project_detail.html', project=project, drawings=drawings, requirements=requirements)

@bp.route('/projects/<int:id>/edit', methods=['GET','POST'])
def project_edit(id):
    project = Project.query.get_or_404(id)
    if request.method == 'POST':
        project.title = request.form.get('title','').strip() or project.title
        project.customer = request.form.get('customer')
        project.revision = request.form.get('revision')
        project.units = request.form.get('units') or project.units
        project.notes = request.form.get('notes')
        db.session.commit()
        if request.headers.get('HX-Request'):
            # Return updated header partial for inline swap
            return render_template('_project_header.html', project=project)
        flash('Project updated.', 'success')
        return redirect(url_for('main.project_detail', id=id))
    # GET
    if request.headers.get('HX-Request'):
        return render_template('_project_edit_form.html', project=project)
    return render_template('project_edit.html', project=project)

@bp.route('/projects/<int:id>/delete', methods=['POST'])
def project_delete(id):
    project = Project.query.get_or_404(id)
    # Remove drawing files from disk
    base = current_app.config['UPLOAD_FOLDER']
    for d in list(project.drawings):
        try:
            path = safe_join(base, d.filename)
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
    # Delete project cascades to drawings/requirements/annotations
    db.session.delete(project)
    db.session.commit()
    flash('Project deleted.', 'success')
    return redirect(url_for('main.index'))

# -------------- Drawings (upload/list) --------------
@bp.route('/projects/<int:id>/drawings', methods=['GET','POST'])
def project_drawings(id):
    project = Project.query.get_or_404(id)
    if request.method == 'POST':
        if not check_upload_rate_limit():
            flash('Upload rate limit reached. Please wait a moment and try again.', 'warning')
            return redirect(url_for('main.project_drawings', id=id))

        if 'pdf' not in request.files:
            flash('No file part.', 'danger')
            return redirect(url_for('main.project_drawings', id=id))
        f = request.files['pdf']
        if f.filename == '':
            flash('No selected file.', 'danger')
            return redirect(url_for('main.project_drawings', id=id))
        if not allowed_file(f.filename):
            flash('Only PDF files are allowed.', 'danger')
            return redirect(url_for('main.project_drawings', id=id))

        # Validate magic bytes
        data = f.read()
        bio = io.BytesIO(data)
        if not pdf_magic_is_valid(bio):
            flash('Invalid PDF file.', 'danger')
            return redirect(url_for('main.project_drawings', id=id))
        # Size check
        if len(data) > current_app.config['MAX_CONTENT_LENGTH']:
            flash('File exceeds size limit.', 'danger')
            return redirect(url_for('main.project_drawings', id=id))

        original_name = f.filename
        safe_name = secure_filename(original_name)
        unique = uuid.uuid4().hex[:8]
        stored_name = f"{unique}_{safe_name}"
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], stored_name)
        with open(path, 'wb') as out:
            out.write(data)

        # Page count
        try:
            reader = PdfReader(io.BytesIO(data))
            page_count = len(reader.pages)
        except Exception:
            page_count = 1

        base_title = os.path.splitext(original_name)[0]
        drawing = Drawing(project_id=id, filename=stored_name, original_name=original_name, page_count=page_count, title=base_title)
        db.session.add(drawing)
        db.session.commit()
        flash('Drawing uploaded.', 'success')
        return redirect(url_for('main.project_drawings', id=id))

    drawings = Drawing.query.filter_by(project_id=id).order_by(Drawing.uploaded_at.desc()).all()
    return render_template('drawings_list.html', project=project, drawings=drawings)

@bp.route('/drawings/<int:id>/edit', methods=['GET','POST'])
def drawing_edit(id):
    d = Drawing.query.get_or_404(id)
    if request.method == 'POST':
        title = request.form.get('title', '').strip() or None
        notes = request.form.get('notes', '').strip() or None
        new_filename = request.form.get('filename', '').strip()

        d.title = title
        d.notes = notes

        if new_filename and new_filename != d.filename:
            if not new_filename.lower().endswith('.pdf'):
                new_filename += '.pdf'
            safe_name = secure_filename(new_filename)
            base = current_app.config['UPLOAD_FOLDER']
            old_path = safe_join(base, d.filename)
            new_path = safe_join(base, safe_name)
            if os.path.exists(new_path):
                name, ext = os.path.splitext(safe_name)
                i = 1
                while True:
                    candidate = f"{name}_{i}{ext}"
                    cand_path = safe_join(base, candidate)
                    if not os.path.exists(cand_path):
                        new_path = cand_path
                        safe_name = candidate
                        break
                    i += 1
            try:
                if old_path and os.path.exists(old_path):
                    os.rename(old_path, new_path)
                d.filename = safe_name
            except Exception as e:
                flash(f'Failed to rename file: {e}', 'danger')
        db.session.commit()
        flash('Drawing updated.', 'success')
        return redirect(url_for('main.drawing_annotate', id=d.id))

    return render_template('drawing_edit.html', drawing=d)

@bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    # Resolve path safely relative to configured upload folder
    base = current_app.config['UPLOAD_FOLDER']
    path = safe_join(base, filename)
    if not path or not os.path.exists(path):
        abort(404)
    return send_file(path)

# -------------- Requirements --------------
@bp.route('/projects/<int:id>/requirements', methods=['GET','POST'])
def project_requirements(id):
    project = Project.query.get_or_404(id)
    if request.method == 'POST':
        # Validate with Marshmallow
        form = request.form.to_dict(flat=False)
        # Flatten HTMX repeated fields like datum_refs[]
        flat = {k.rstrip('[]'): (v if len(v) > 1 else v[0]) for k,v in form.items()}
        # Normalize datum list
        datums = request.form.getlist('datum_refs[]')
        flat['datum_refs'] = datums or None
        # Normalize booleans/numerics
        flat['diameter_modifier_bool'] = True if request.form.get('diameter_modifier_bool') == 'on' else False
        # Decimal tolerance
        tol = request.form.get('tolerance_value')
        if tol:
            try:
                flat['tolerance_value'] = str(Decimal(tol))
            except InvalidOperation:
                flat['tolerance_value'] = None

        schema = RequirementSchema()
        data = schema.load(flat)

        # Build FCF text for preview/storage
        fcf = build_fcf_text(
            data['symbol_key'],
            Decimal(data['tolerance_value']) if data.get('tolerance_value') else None,
            data.get('tolerance_unit'),
            data.get('diameter_modifier_bool', False),
            data.get('material_condition'),
            data.get('datum_refs')
        )
        r = Requirement(
            project_id=project.id,
            title=data['title'],
            feature_name=data.get('feature_name'),
            description=data.get('description'),
            symbol_key=data['symbol_key'],
            tolerance_value=Decimal(data['tolerance_value']) if data.get('tolerance_value') else None,
            tolerance_unit=data.get('tolerance_unit'),
            diameter_modifier_bool=data.get('diameter_modifier_bool', False),
            material_condition=data.get('material_condition'),
            datum_refs=data.get('datum_refs'),
            zone_shape=data.get('zone_shape'),
            fcf_text=fcf,
            notes=data.get('notes')
        )
        db.session.add(r)
        db.session.commit()
        flash('Requirement added.', 'success')
        return redirect(url_for('main.project_requirements', id=id))

    # GET: list + create form
    requirements = Requirement.query.filter_by(project_id=id).order_by(Requirement.created_at.desc()).all()
    return render_template('requirements_list.html', project=project, requirements=requirements)

@bp.route('/requirements/<int:id>', methods=['GET','POST'])
def requirement_detail(id):
    r = Requirement.query.get_or_404(id)
    if request.method == 'POST':
        # Simple updates
        r.title = request.form.get('title', r.title)
        r.description = request.form.get('description', r.description)
        r.notes = request.form.get('notes', r.notes)
        db.session.commit()
        flash('Requirement updated.', 'success')
    explanation = explain_requirement(r)
    return render_template('requirement_detail.html', r=r, explanation=explanation)

# Live FCF preview (HTMX endpoint)
@bp.route('/fcf/preview', methods=['POST'])
@csrf.exempt
def fcf_preview():
    form = request.form
    symbol_key = form.get('symbol_key') or 'position'
    tol_val = form.get('tolerance_value')
    tol = None
    if tol_val:
        try:
            tol = Decimal(tol_val)
        except Exception:
            tol = None
    unit = form.get('tolerance_unit')
    diameter = form.get('diameter_modifier_bool') == 'on'
    material = form.get('material_condition')
    datums = form.getlist('datum_refs[]')
    fcf = build_fcf_text(symbol_key, tol, unit, diameter, material, datums)
    explanation = f"{symbol_key.title()} — " + ("diametral zone; " if diameter else "") + (f"{tol} {unit}" if tol else "") + (f" at {material}" if material else "")
    return render_template('_fcf_preview.html', fcf=fcf, explanation=explanation)

# -------------- PDF viewer & annotations --------------
@bp.route('/drawings/<int:id>/view')
def drawing_view(id):
    drawing = Drawing.query.get_or_404(id)
    page = max(0, int(request.args.get('page', '0')))
    if page >= drawing.page_count:
        page = drawing.page_count - 1
    # Annotations for this page
    anns = Annotation.query.filter_by(drawing_id=drawing.id, page_index=page).all()
    anns_json = AnnotationSchema(many=True).dump(anns)
    return render_template('drawing_view.html', drawing=drawing, page=page, annotations_json=anns_json)

@bp.route('/drawings/<int:id>/annotate')
def drawing_annotate(id):
    drawing = Drawing.query.get_or_404(id)
    page = max(0, int(request.args.get('page', '0')))
    if page >= drawing.page_count:
        page = drawing.page_count - 1
    # All project requirements to link
    reqs = Requirement.query.filter_by(project_id=drawing.project_id).order_by(Requirement.created_at.desc()).all()
    anns = Annotation.query.filter_by(drawing_id=drawing.id, page_index=page).all()
    anns_json = AnnotationSchema(many=True).dump(anns)
    return render_template('drawing_annotate.html', drawing=drawing, page=page, requirements=reqs, annotations=anns, annotations_json=anns_json)

@bp.route('/drawings/<int:id>/delete', methods=['POST'])
def drawing_delete(id):
    d = Drawing.query.get_or_404(id)
    project_id = d.project_id
    # Remove file from disk if present
    try:
        base = current_app.config['UPLOAD_FOLDER']
        path = safe_join(base, d.filename)
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
    # Delete DB row (annotations cascade via FK)
    db.session.delete(d)
    db.session.commit()
    flash('Drawing deleted.', 'success')
    return redirect(url_for('main.project_drawings', id=project_id))

@bp.route('/annotations', methods=['POST'])
@csrf.exempt
def create_annotation():
    # HTMX post
    raw = request.get_json(silent=True) or {}
    schema = AnnotationSchema()
    data = schema.load(raw)
    a = Annotation(
        requirement_id=data['requirement_id'],
        drawing_id=data['drawing_id'],
        page_index=data['page_index'],
        kind=data['kind'],
        coords_json=data['coords_json'],
        label=data.get('label'),
        color_hex=data.get('color_hex') or '#ff0066'
    )
    db.session.add(a)
    db.session.commit()
    return jsonify({'ok': True, 'annotation_id': a.id})

@bp.route('/annotations/list')
def list_annotations():
    drawing_id = int(request.args.get('drawing_id'))
    page_index = int(request.args.get('page_index'))
    anns = Annotation.query.filter_by(drawing_id=drawing_id, page_index=page_index).all()
    return render_template('_annotation_list.html', annotations=anns)

@bp.route('/api/annotations/hit')
def api_hit_test():
    drawing_id = int(request.args.get('drawing_id'))
    page_index = int(request.args.get('page_index'))
    x = float(request.args.get('x'))
    y = float(request.args.get('y'))
    anns = Annotation.query.filter_by(drawing_id=drawing_id, page_index=page_index).all()
    for a in anns:
        d = {'kind': a.kind, 'coords_json': a.coords_json}
        if hit_test(d, x, y):
            return jsonify({'hit': True, 'requirement_id': a.requirement_id, 'annotation_id': a.id})
    return jsonify({'hit': False})

# Partial card for requirement drawer (HTMX)
@bp.route('/requirements/<int:id>/card')
def requirement_card(id):
    r = Requirement.query.get_or_404(id)
    explanation = explain_requirement(r)
    return render_template('_requirement_card.html', r=r, explanation=explanation)

# -------------- Symbols Palette --------------
@bp.route('/symbols')
def symbols():
    # Load knowledge
    path = os.path.join(current_app.root_path, 'knowledge', 'gdt_knowledge.json')
    with open(path, 'r') as f:
        kb = json.load(f)
    # Ensure inline SVG renders as markup, not text
    try:
        for s in kb.get('symbols', []):
            val = s.get('unicode_glyph_or_svg')
            if isinstance(val, str) and val.lstrip().startswith('<svg'):
                s['unicode_glyph_or_svg'] = Markup(val)
    except Exception:
        pass
    return render_template('symbols.html', kb=kb)

# -------------- Insights --------------
@bp.route('/insights')
def insights():
    project_id = int(request.args.get('project'))
    project = Project.query.get_or_404(project_id)
    reqs = Requirement.query.filter_by(project_id=project_id).all()
    items = compute_insights(project, reqs)
    return render_template('insights.html', project=project, items=items)

# -------------- Search --------------
@bp.route('/search')
def search():
    q = request.args.get('q', '').strip()
    symbol = request.args.get('symbol')
    has_ann = request.args.get('has_annotation')
    project_id = request.args.get('project_id', type=int)

    req_query = Requirement.query
    if project_id:
        req_query = req_query.filter(Requirement.project_id == project_id)

    if q:
        like = f"%{q}%"
        req_query = req_query.filter(or_(
            Requirement.title.ilike(like),
            Requirement.feature_name.ilike(like),
            Requirement.description.ilike(like),
            Requirement.fcf_text.ilike(like),
            func.cast(Requirement.datum_refs, db.String).ilike(like)
        ))
    if symbol:
        req_query = req_query.filter(Requirement.symbol_key == symbol)
    if has_ann == '1':
        req_query = req_query.join(Annotation).distinct()

    results = req_query.order_by(Requirement.created_at.desc()).all()
    return render_template('requirements_list.html', project=None, requirements=results, search_mode=True, query=q)

# -------------- Export --------------
@bp.route('/export/csv')
def export_csv():
    import csv
    project_id = int(request.args.get('project'))
    project = Project.query.get_or_404(project_id)
    reqs = Requirement.query.filter_by(project_id=project_id).order_by(Requirement.id.asc()).all()

    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(['id','title','feature','symbol','fcf','tol_value','tol_unit','diameter','material','datums','zone','notes','linked_pages'])
    for r in reqs:
        pages = sorted({a.page_index+1 for a in r.annotations})
        w.writerow([
            r.id, r.title, r.feature_name or '', r.symbol_key, r.fcf_text or '',
            str(r.tolerance_value or ''), r.tolerance_unit or '', 'Y' if r.diameter_modifier_bool else '',
            r.material_condition or '', '|'.join(r.datum_refs or []), r.zone_shape or '', r.notes or '',
            ','.join(map(str,pages))
        ])
    output.seek(0)
    filename = f"project_{project_id}_requirements.csv"
    return send_file(io.BytesIO(output.getvalue().encode('utf-8')), as_attachment=True, download_name=filename, mimetype='text/csv')

@bp.route('/export/report')
def export_report():
    project_id = int(request.args.get('project'))
    project = Project.query.get_or_404(project_id)
    reqs = Requirement.query.filter_by(project_id=project_id).order_by(Requirement.id.asc()).all()

    # Build lightweight PDF using reportlab
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=f"GD&T Report — {project.title}")
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph(f"<b>GD&amp;T Helper Report</b>", styles['Title']))
    story.append(Paragraph(f"Project: {project.title}", styles['Normal']))
    story.append(Paragraph(f"Customer: {project.customer or '-'} | Rev: {project.revision or '-'} | Units: {project.units}", styles['Normal']))
    story.append(Spacer(1, 12))

    data = [['ID','Title','Symbol','FCF','Tol','Mat','Datums','Pages']]
    for r in reqs:
        pages = sorted({a.page_index+1 for a in r.annotations})
        data.append([r.id, r.title, r.symbol_key, r.fcf_text or '', str(r.tolerance_value or ''), r.material_condition or '', ' | '.join(r.datum_refs or []), ','.join(map(str,pages))])
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0), colors.lightgrey),
        ('GRID',(0,0),(-1,-1), 0.25, colors.grey),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold')
    ]))
    story.append(t)
    story.append(Spacer(1, 12))
    story.append(Paragraph("Note: Thumbnails are omitted unless snapshots are provided via future enhancement.", styles['Italic']))

    doc.build(story)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f"project_{project_id}_report.pdf", mimetype='application/pdf')

# -------------- Help / User Guide --------------
@bp.route('/help/user-guide')
def user_guide():
    return render_template('user_guide.html')
