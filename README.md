# GD&T Helper (Local)

A single-user, local-only Flask web app to organize GD&T requirements against drawing PDFs, map clickable annotations, browse a symbols palette, view insights, and export CSV/PDF reports.

> **Privacy & scope**: No login, no external calls, no multi-user. By default, the server binds to `127.0.0.1` only.

---

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Initialize database (SQLite by default)
flask db upgrade
flask seed

# Run (binds to 127.0.0.1)
flask run
```

Open http://127.0.0.1:5000/

### Environment (.env)

Copy `.env.example` to `.env` and adjust if needed. Important keys:

- `DATABASE_URL` — default `sqlite:///gdt_helper.db` (created in the project root). You can switch to Postgres later.
- `UPLOAD_FOLDER` — where PDFs are stored (default `uploads/`).
- `MAX_CONTENT_LENGTH_MB` — file size limit per PDF (default 25).

### Tech

- Flask, SQLAlchemy, Flask-Migrate, Marshmallow, python-dotenv, Flask-WTF (CSRF)
- Jinja2 + Bootstrap 5 + Bootstrap Icons
- HTMX for snappy UX (no SPA)
- PDF.js (via CDN) + overlay (HTML/SVG) for clickable annotations
- SQLite by default (Postgres-ready via `DATABASE_URL`)

---

## In-app User Guide

Inside the app, open **Help → User Guide** (top-right) for a step-by-step workflow:
1. Create a project.
2. Upload drawings (PDF).
3. Add requirements using the FCF builder.
4. Annotate the drawing (box or polygon) and link to a requirement.
5. Click any mapped region in the viewer to jump to a requirement with a plain-English explanation.
6. Check **Insights** for relationships, mistakes, and bonus tolerance at MMC/LMC.
7. Export CSV or a lightweight PDF report.

---

## Tests

```bash
pytest -q
```

Tests cover:
- FCF build preview (e.g., hole at MMC with datums A|B|C).
- Insights (flags symmetry/concentricity usage with modern alternatives).
- Annotation hit-test on page 2 with polygon.
- Export CSV rows match the requirement count.

---

## Security & Safety (Local)

- CSRF protection on form posts (even though single-user).
- PDF validation: extension + mimetype + magic bytes signature (`%PDF`), 25 MB limit.
- Simple in-process rate-limit for uploads.
- App warns in the UI if environment host is changed away from `127.0.0.1`.

---

## Notes

- The PDF report is intentionally lightweight (tables and summary). Thumbnails of annotated regions are included if snapshots are present; otherwise the report lists region metadata (page, kind, label).
- You can switch to Postgres later by setting `DATABASE_URL` to a valid SQLAlchemy URL.
