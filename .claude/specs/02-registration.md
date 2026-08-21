# Spec: Registration

## Overview
This step wires up the `/register` route with a real POST handler so new users
can create an account. The form already exists in `register.html` — this spec
adds the backend: validation, duplicate-email check, password hashing, DB insert,
and a session cookie so the user is logged in immediately after signing up.
This is the first route that writes to the database and establishes the Flask
`session` pattern used by all subsequent authenticated routes.

## Depends on
- Step 1 — Database setup (`database/db.py` fully implemented with `users` table)

## Routes
- `GET  /register` — render the registration form — public
- `POST /register` — validate input, create user, set session, redirect to `/profile` — public

## Database changes
No database changes. The `users` table created in Step 1 already has all required
columns: `id`, `name`, `email`, `password_hash`, `created_at`.

## Templates
- **Modify:** `templates/register.html`
  - Form already renders correctly; no structural changes needed
  - Ensure `{{ error }}` flash block is present (already in template)
  - Re-populate `name` and `email` fields with `{{ request.form.name }}` /
    `{{ request.form.email }}` on validation failure so the user doesn't retype them

## Files to change
- `app.py` — convert `register()` to accept GET and POST; add full handler logic
- `templates/register.html` — add `value="{{ request.form.name }}"` and
  `value="{{ request.form.email }}"` to the name and email inputs

## Files to create
No new files.

## New dependencies
No new dependencies. `flask.session` and `werkzeug.security` are already available.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never string-format SQL
- Passwords hashed with `werkzeug.security.generate_password_hash`; never store plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Set `app.secret_key` in `app.py` (required for `session` to work); use a hardcoded
  dev string for now — `"spendly-dev-secret"` — noted as a TODO for production
- After successful registration, store `session["user_id"]` and `session["user_name"]`
- Redirect to `/profile` on success (even though `/profile` is still a placeholder)
- On failure, re-render `register.html` and pass `error=` with a human-readable message
- Validate: name non-empty, email non-empty, password ≥ 8 characters
- Check for duplicate email with a SELECT before INSERT; return a friendly error if taken
- Use `get_db()` — open and close the connection within the request; do not keep it open

## Definition of done
- [ ] Visiting `/register` (GET) renders the form with no errors
- [ ] Submitting valid name / email / password creates a new row in `users`
- [ ] After registration, the browser is redirected to `/profile`
- [ ] `session["user_id"]` is set and matches the newly inserted user's `id`
- [ ] Submitting with an email already in the database shows "Email already registered"
- [ ] Submitting with a password shorter than 8 characters shows a validation error
- [ ] Submitting with an empty name shows a validation error
- [ ] After a failed submission, the name and email fields are pre-filled with what the user typed
- [ ] The password field is always empty after a failed submission (never echo passwords)
- [ ] Running `/seed-user` then registering with the seeded email is correctly rejected
