# Spec: Login and Logout

## Overview
This step wires up the `/login` route with a real POST handler and implements
`/logout` so users can sign in and out of their accounts. The login form already
exists in `login.html` — this spec adds the backend: email/password validation,
credential verification against the database using `check_password_hash`, session
establishment on success, and full session teardown on logout. Together these two
routes complete the authentication lifecycle started by `/register` in Step 2,
enabling all subsequent authenticated routes to gate access via `session["user_id"]`.

## Depends on
- Step 1 — Database setup (`database/db.py` fully implemented with `users` table)
- Step 2 — Registration (`/register` POST handler, `session["user_id"]` pattern established)

## Routes
- `GET  /login`  — render the login form — public
- `POST /login`  — validate credentials, set session, redirect to `/profile` — public
- `GET  /logout` — clear session, redirect to `/` — logged-in (but safe to call when logged out)

## Database changes
No database changes. The `users` table already has all required columns:
`id`, `name`, `email`, `password_hash`.

## Templates
- **Modify:** `templates/login.html`
  - Add `value="{{ request.form.get('email', '') }}"` to the email input so the
    email field is sticky on failed login
  - Password field must never be pre-filled

## Files to change
- `app.py`
  - Add `check_password_hash` to the `werkzeug.security` import
  - Convert `login()` to accept `GET` and `POST`
  - Implement `/logout` route (replace placeholder string)
- `templates/login.html` — sticky email value on validation failure

## Files to create
No new files.

## New dependencies
No new dependencies. `check_password_hash` is already in `werkzeug.security`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never string-format SQL
- Passwords verified with `werkzeug.security.check_password_hash`; never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Login POST handler flow:
  1. Extract and strip `email` and `password` from `request.form`
  2. Validate both fields are non-empty; re-render `login.html` with `error=` on failure
  3. Fetch user row by email: `SELECT id, name, password_hash FROM users WHERE email = ?`
  4. If no row found, return generic error: `"Invalid email or password."` (never reveal which field is wrong)
  5. Call `check_password_hash(row["password_hash"], password)`; return same generic error on mismatch
  6. On success: set `session["user_id"] = row["id"]` and `session["user_name"] = row["name"]`
  7. Redirect to `url_for("profile")`
- Logout handler: call `session.clear()`, then `return redirect(url_for("landing"))`
- Use `get_db()` — open and close the connection within the request; do not keep it open
- Generic error message on credential failure prevents user enumeration attacks

## Definition of done
- [ ] Visiting `/login` (GET) renders the form with no errors
- [ ] Submitting a valid email and correct password sets `session["user_id"]` and `session["user_name"]`
- [ ] After successful login, the browser is redirected to `/profile`
- [ ] Submitting with a valid email but wrong password shows `"Invalid email or password."`
- [ ] Submitting with an email not in the database shows `"Invalid email or password."` (same message)
- [ ] Submitting with an empty email or empty password shows a validation error
- [ ] After a failed login, the email field is pre-filled with what the user typed
- [ ] The password field is always empty after a failed submission
- [ ] Visiting `/logout` clears the session and redirects to the landing page `/`
- [ ] Visiting `/logout` when not logged in also redirects to `/` without error
- [ ] The demo user (`demo@spendly.com` / `demo123`) can log in successfully
