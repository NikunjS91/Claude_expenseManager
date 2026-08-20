# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
source venv/bin/activate
python app.py          # runs on http://localhost:5001
```

## Testing

```bash
pytest                 # run all tests
pytest tests/test_foo.py::test_name  # single test
```

## Architecture

**Spendly** is a Flask-based expense tracker built as a CampusX course project. Students implement features incrementally — many routes in `app.py` currently return placeholder strings and are meant to be completed step-by-step.

### Key files

- `app.py` — all routes; placeholder routes are marked with "coming in Step N" comments
- `templates/base.html` — shared layout with navbar and footer; all other templates extend this
- `static/css/style.css` — global design system (fonts: DM Serif Display + DM Sans)
- `static/css/landing.css` — landing-page-only styles (loaded via `{% block head %}`)
- `static/js/main.js` — shared JS
- `database/db.py` — stub only; students implement three functions here (see below)

### Template pattern

Templates extend `base.html` and override `{% block title %}`, `{% block content %}`, optionally `{% block head %}` (page-specific CSS/JS loaded in `<head>`), and optionally `{% block scripts %}` (JS loaded before `</body>`).

### Database layer (`database/db.py`)

Students must implement three functions:

- `get_db()` — returns a SQLite connection with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`
- `init_db()` — creates all tables using `CREATE TABLE IF NOT EXISTS`
- `seed_db()` — inserts sample rows for development

### Student step roadmap

| Step | Feature |
|------|---------|
| 1 | Database setup (`database/db.py`) |
| 2 | Wire `init_db` / `get_db` into `app.py` |
| 3 | `/logout` — session teardown |
| 4 | `/profile` — user profile page |
| 7 | `/expenses/add` |
| 8 | `/expenses/<id>/edit` |
| 9 | `/expenses/<id>/delete` |

### Implemented routes

| Route | Status |
|-------|--------|
| `/` | landing page with hero + video modal |
| `/login`, `/register` | auth forms (UI only, no backend yet) |
| `/terms`, `/privacy` | static legal pages |
| `/logout`, `/profile`, `/expenses/*` | placeholder strings — student TODO |
