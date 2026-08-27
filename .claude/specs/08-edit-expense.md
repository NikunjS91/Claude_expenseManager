# Spec: Edit Expense

## Overview
Step 8 implements the `/expenses/<id>/edit` route so logged-in users can correct
or update an expense they previously recorded. The route currently returns a
placeholder string. This step replaces it with a GET handler that pre-populates a
form with the existing expense data and a POST handler that validates the updated
input, writes it back to the `expenses` table, and redirects to `/profile`. This
closes the CRUD loop for expenses — after Step 7 (create), users can now fix
mistakes without deleting and re-entering data.

## Depends on
- Step 1: Database setup (`expenses` table must exist)
- Step 2: Registration (session pattern established)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 5: Backend connection (`get_db()` available, query helpers in place)
- Step 7: Add Expense (expenses exist in the database to edit; same form design to mirror)

## Routes
- `GET  /expenses/<int:id>/edit` — fetch the expense row and render a pre-populated edit form — logged-in only
- `POST /expenses/<int:id>/edit` — validate updated input, UPDATE the row, redirect to `/profile` — logged-in only

## Database changes
No database changes. The `expenses` table already has all required columns:
`id`, `user_id`, `amount`, `category`, `date`, `description`, `created_at`.

## Templates
- **Create:** `templates/edit_expense.html`
  - Extends `base.html`
  - Form with `method="POST"` and `action="{{ url_for('edit_expense', id=expense.id) }}"`
  - Fields pre-populated from the fetched expense row:
    - `amount` — `<input type="number" step="0.01" min="0.01">` — required
    - `category` — category pill selector (same as add_expense.html) — required
    - `date` — `<input type="date">` — required
    - `description` — `<input type="text">` — optional, max 200 characters
  - Submit button: "Save Changes"
  - Error display block for validation messages
  - On validation failure: re-populate fields from `request.form` (not from DB)
  - Link back to `/profile` ("Cancel")

## Files to change
- `app.py`
  - Convert `edit_expense()` to accept both `GET` and `POST`
  - Add auth guard: redirect to `/login` if `session.get("user_id")` is absent
  - GET: fetch the expense by `id` WHERE `user_id = session["user_id"]`; 404 if not found or belongs to another user; render `edit_expense.html` with expense data
  - POST: validate, UPDATE the row (only if `user_id` matches session), redirect to `/profile` with a success flash message

## Files to create
- `templates/edit_expense.html` — the edit-expense form template

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Passwords hashed with werkzeug (no changes to auth in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Auth guard on both GET and POST: `if not session.get("user_id"): redirect(url_for("login"))`
- Ownership check: always include `AND user_id = ?` in the SELECT and UPDATE — a user must never be able to view or edit another user's expense; return 404 if the expense is not found or does not belong to the logged-in user
- Validation rules for POST (same as Step 7):
  - `amount`: must be present, must convert to a positive finite float greater than 0
  - `category`: must be one of the seven fixed values (whitelist check via `CATEGORY_NAMES`)
  - `date`: must be present and parseable as `YYYY-MM-DD` via `parse_date()`
  - `description`: optional; strip whitespace; truncate to 200 chars
- On any validation failure: re-render `edit_expense.html` with an `error=` message and re-populate all fields from `request.form`
- On success: UPDATE the row, call `flash("Expense updated successfully.", "success")`, then `redirect(url_for("profile"))`
- `user_id` must never be updated — only `amount`, `category`, `date`, `description` are writable
- Use `get_db()` — open and close the connection within the request
- Reuse the `CATEGORIES` list and `CATEGORY_NAMES` constant already defined in `app.py`
- Reuse the `parse_date()` helper already defined in `app.py`

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` without being logged in redirects to `/login`
- [ ] Visiting `/expenses/<id>/edit` for an expense that does not exist returns 404
- [ ] Visiting `/expenses/<id>/edit` for an expense belonging to another user returns 404
- [ ] Visiting `/expenses/<id>/edit` while logged in and owning the expense returns HTTP 200 and renders a pre-populated form
- [ ] All four fields (amount, category, date, description) are pre-populated with the expense's current values when the form loads
- [ ] Submitting valid updated values writes the changes to the `expenses` table
- [ ] After a successful update, the browser is redirected to `/profile` and a success flash message is visible
- [ ] The updated expense values appear in the transaction list on `/profile` after redirect
- [ ] Submitting with a missing or zero amount shows a validation error and re-renders the form
- [ ] Submitting with a negative amount shows a validation error
- [ ] Submitting with an invalid category shows a validation error
- [ ] Submitting with a missing or malformed date shows a validation error
- [ ] After a failed submission, all previously entered values are pre-filled in the form (sticky form)
- [ ] The `user_id` on the expense row is never changed by the edit operation
- [ ] A user cannot edit another user's expense by crafting a direct URL to `/expenses/<id>/edit`
