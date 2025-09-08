# GD&T Helper (Local)

A single-user, local-only Flask web app to organize GD&T requirements against drawing PDFs, map clickable annotations, browse a symbols palette, view insights, and export CSV/PDF reports.

> **Privacy & scope**: No login, no external calls, no multi-user. By default, the server binds to `127.0.0.1` only.

---

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Initialize the database (SQLite by default)
# IMPORTANT: Apply migrations before running the app, otherwise you'll see
# "sqlite3.OperationalError: no such table: project" on the homepage.
flask db upgrade

# Optional: load demo data and sample PDFs
flask seed

# Run (binds to 127.0.0.1)
flask run
```

Open http://127.0.0.1:5000/

### Environment (.env)

Copy `.env.example` to `.env` and adjust if needed. Important keys:

- `DATABASE_URL` — default `sqlite:///instance/gdt_helper.db` so the DB lives under `instance/` (kept out of version control by default). You can switch to Postgres later.
- `UPLOAD_FOLDER` — where PDFs are stored (default `uploads/`).
- `MAX_CONTENT_LENGTH_MB` — file size limit per PDF (default 25).

### Tech

- Flask, SQLAlchemy, Flask-Migrate, Marshmallow, python-dotenv, Flask-WTF (CSRF)
- Jinja2 + Bootstrap 5 + Bootstrap Icons
- HTMX for snappy UX (no SPA)
- PDF.js (via CDN) + overlay (HTML/SVG) for clickable annotations
- SQLite by default (Postgres-ready via `DATABASE_URL`)

---

## Troubleshooting

- Error: `sqlite3.OperationalError: no such table: project`
  - Cause: The database file exists but migrations have not been applied.
  - Fix: Activate your venv and run `flask db upgrade`, then optionally `flask seed`.
  - Verify: You should now see `project`, `drawing`, `requirement`, and `annotation` tables in the DB.

- Where is the DB file?
  - By default `.env.example` points `DATABASE_URL` to `sqlite:///instance/gdt_helper.db`.
  - If you previously used `sqlite:///gdt_helper.db` in the project root, switch your `.env` to the `instance/` path and run `flask db upgrade` again.

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
# GD&T Helper (Local)

A single-user, local-only Flask web app to organize GD&T requirements against drawing PDFs, map clickable annotations, browse a symbols palette, view insights, and export CSV/PDF reports.

> **Privacy & scope**: No login, no external calls, no multi-user. By default, the server binds to `127.0.0.1` only.

---

## Quickstart

```bash
# Install uv (https://astral.sh/uv) if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create a virtual environment and install dependencies
uv venv
uv pip install -r requirements.txt

# Initialize database (SQLite by default)
uv run flask db upgrade
uv run flask seed

# Run (binds to 127.0.0.1)
uv run flask run
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

## Troubleshooting

- Error: `sqlite3.OperationalError: no such table: project`
  - Run migrations: `uv run flask db upgrade`
  - Or create tables directly: `uv run flask init-db`
  - Then seed: `uv run flask seed`

- Error: "The CSRF token is missing"
  - CSRF is enabled by default. Forms now include a hidden token automatically.
  - HTMX/JS requests attach the token via `X-CSRFToken` header.
  - To disable for local/testing, set `WTF_CSRF_ENABLED=false` in `.env` and restart.

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
uv run pytest -q
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
