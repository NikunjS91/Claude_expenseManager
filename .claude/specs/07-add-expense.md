# Spec: Add Expense

## Overview
Step 7 implements the `/expenses/add` route so logged-in users can record a new
expense. The route currently returns a placeholder string. This step replaces it
with a GET handler that renders a form and a POST handler that validates the input,
inserts a row into the `expenses` table, and redirects back to `/profile`. This is
the first route that lets users write their own data to the database, completing
the core data-entry loop of the Spendly expense tracker.

## Depends on
- Step 1: Database setup (`expenses` table with `user_id`, `amount`, `category`,
  `date`, `description` columns must exist)
- Step 2: Registration (session pattern established)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 5: Backend connection (query helpers in `database/queries.py` exist; profile
  page will reflect the newly added expense after redirect)

## Routes
- `GET  /expenses/add` — render the add-expense form — logged-in only
- `POST /expenses/add` — validate input, insert expense row, redirect to `/profile` — logged-in only

## Database changes
No database changes. The `expenses` table already has all required columns:
`id`, `user_id`, `amount`, `category`, `date`, `description`, `created_at`.

## Templates
- **Create:** `templates/add_expense.html`
  - Extends `base.html`
  - Form with `method="POST"` and `action="{{ url_for('add_expense') }}"`
  - Fields:
    - `amount` — `<input type="number" step="0.01" min="0.01">` — required
    - `category` — `<select>` with the seven fixed categories: Food, Transport,
      Bills, Health, Entertainment, Shopping, Other — required
    - `date` — `<input type="date">` — required; default to today's date
    - `description` — `<input type="text">` — optional, max 200 characters
  - Submit button: "Add Expense"
  - Error display block for validation messages
  - On validation failure: re-populate `amount`, `category`, `date`, and
    `description` from `request.form` so the user doesn't retype everything
  - Link back to `/profile` ("Cancel")

## Files to change
- `app.py`
  - Convert `add_expense()` to accept both `GET` and `POST`
  - Add auth guard: redirect to `/login` if `session.get("user_id")` is absent
  - GET: render `add_expense.html` with today's date pre-filled
  - POST: validate, insert, redirect to `/profile` with a success flash message

## Files to create
- `templates/add_expense.html` — the add-expense form template

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
- Validation rules for POST:
  - `amount`: must be present, must convert to a positive float greater than 0
  - `category`: must be one of the seven fixed values (whitelist check)
  - `date`: must be present and parseable as `YYYY-MM-DD` via `datetime.strptime`
  - `description`: optional; strip whitespace; truncate or reject if over 200 chars
- On any validation failure: re-render `add_expense.html` with an `error=` message
  and re-populate all fields from `request.form`
- On success: insert the row, call `flash("Expense added successfully.", "success")`,
  then `redirect(url_for("profile"))`
- `user_id` for the insert must always come from `session["user_id"]` — never from form data
- Fixed category whitelist: `["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]`
- Use `get_db()` — open and close the connection within the request

## Definition of done
- [ ] Visiting `/expenses/add` without being logged in redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in returns HTTP 200 and renders a form
- [ ] The date field defaults to today's date when the form is first loaded
- [ ] Submitting a valid amount, category, date (and optional description) inserts
  a new row in the `expenses` table linked to the logged-in user
- [ ] After a successful insert, the browser is redirected to `/profile` and a
  success flash message is visible
- [ ] The new expense appears in the transaction list on `/profile` after redirect
- [ ] Submitting with a missing or zero amount shows a validation error and re-renders the form
- [ ] Submitting with a negative amount shows a validation error
- [ ] Submitting with an invalid category (e.g. one not in the whitelist) shows a validation error
- [ ] Submitting with a missing date shows a validation error
- [ ] After a failed submission, all previously entered values (amount, category,
  date, description) are pre-filled in the form
- [ ] The `user_id` stored in the new expense row matches `session["user_id"]` —
  a user cannot insert expenses for another user
