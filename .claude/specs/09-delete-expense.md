# Spec: Delete Expense

## Overview
Step 9 implements the `/expenses/<id>/delete` route so logged-in users can remove
an expense they no longer want. The route currently returns a placeholder string.
This step replaces it with a POST-only handler that verifies ownership, deletes the
row from the `expenses` table, and redirects back to `/profile` with a confirmation
flash message. A delete button is added to the profile transaction table alongside
the existing Edit link, completing the full CRUD surface for expenses.

## Depends on
- Step 1: Database setup (`expenses` table must exist)
- Step 2: Registration (session pattern established)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 5: Backend connection (`get_db()` available)
- Step 7: Add Expense (expenses exist to delete)
- Step 8: Edit Expense (profile table already has an actions column with Edit link)

## Routes
- `POST /expenses/<int:expense_id>/delete` — verify ownership, DELETE the row, redirect to `/profile` — logged-in only

No GET handler is needed. Destructive actions must not be triggered by a plain link (GET request) — the delete button in the profile table is wrapped in a `<form method="POST">` so the browser sends a POST.

## Database changes
No database changes. The `expenses` table already has all required columns.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html`
  - Add a Delete button next to the existing Edit link in the `.tx-actions` column
  - The Delete button is a `<form method="POST">` wrapping a submit button, so no JavaScript is required
  - The form `action` points to `url_for('delete_expense', expense_id=tx.id)`

## Files to change
- `app.py`
  - Convert `delete_expense()` to accept `POST` only
  - Rename parameter `id` → `expense_id` (consistent with `edit_expense`)
  - Add auth guard: redirect to `/login` if `session.get("user_id")` is absent
  - Fetch the expense by `expense_id AND user_id` — `abort(404)` if not found or not owned
  - Execute `DELETE FROM expenses WHERE id = ? AND user_id = ?`
  - Flash "Expense deleted successfully." and redirect to `/profile`
- `templates/profile.html`
  - Add delete form button in `.tx-actions` cell after the Edit link
- `static/css/style.css`
  - Add `.tx-delete-btn` style — a small unstyled button that looks like a muted link, turns danger red on hover

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Passwords hashed with werkzeug (no changes to auth in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- The route must only accept `POST` — set `methods=["POST"]` on the route decorator
- Auth guard: `if not session.get("user_id"): redirect(url_for("login"))`
- Ownership check: `DELETE FROM expenses WHERE id = ? AND user_id = ?` — never delete by id alone
- Return `abort(404)` if the expense doesn't exist or belongs to another user (check rowcount after DELETE, or SELECT before)
- Use `get_db()` — open and close the connection within the request
- Rename route parameter `id` → `expense_id` to avoid shadowing Python's built-in `id()`

## Definition of done
- [ ] Sending a POST to `/expenses/<id>/delete` without being logged in redirects to `/login`
- [ ] Sending a POST to `/expenses/<id>/delete` for a non-existent id returns 404
- [ ] Sending a POST to `/expenses/<id>/delete` for another user's expense returns 404 and does NOT delete the row
- [ ] Sending a POST to `/expenses/<id>/delete` for an owned expense removes the row from the `expenses` table
- [ ] After a successful delete, the browser is redirected to `/profile` with the flash message "Expense deleted successfully."
- [ ] The deleted expense no longer appears in the transaction list on `/profile`
- [ ] A Delete button is visible next to each Edit link in the profile transaction table
- [ ] Clicking Delete submits a POST (not a GET) — the delete button is inside a `<form method="POST">`
- [ ] Navigating directly to `/expenses/<id>/delete` in a browser (GET) returns 405 Method Not Allowed
- [ ] Other expenses are not affected — only the targeted row is removed
