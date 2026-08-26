"""
tests/test_07-add-expense.py

Pytest tests for Step 7: Add Expense (/expenses/add route).

Spec: .claude/specs/07-add-expense.md

Setup strategy:
- DB_PATH is patched to a temp file so the real spendly.db is never touched.
- A fresh test user is inserted before each test that needs one.
- Session is seeded directly via client.session_transaction() to simulate login
  without going through the login form.
- All tests are fully independent — no shared mutable state.
"""

import sqlite3
import tempfile
import os
from datetime import date

import pytest

import database.db as db_module
from app import app as flask_app
from database.db import init_db


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def app(tmp_path):
    """
    Yield the Flask app configured for testing.

    DB_PATH is patched to a temp SQLite file so no real data is touched.
    init_db() creates a clean schema before each test and the temp file
    is removed automatically when the test ends.
    """
    db_file = str(tmp_path / "test_spendly.db")
    original_db_path = db_module.DB_PATH
    db_module.DB_PATH = db_file

    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "WTF_CSRF_ENABLED": False,
    })

    with flask_app.app_context():
        init_db()
        yield flask_app

    db_module.DB_PATH = original_db_path


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def test_user(app):
    """
    Insert a test user directly into the DB and return their id and credentials.
    Uses raw sqlite3 to stay independent of app-layer helpers.
    """
    from werkzeug.security import generate_password_hash
    conn = sqlite3.connect(db_module.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Test User", "test@spendly.com", generate_password_hash("testpass123")),
    )
    conn.commit()
    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return {"id": user_id, "name": "Test User", "email": "test@spendly.com"}


@pytest.fixture
def auth_client(client, test_user):
    """Test client with a real test user already in session."""
    with client.session_transaction() as sess:
        sess["user_id"] = test_user["id"]
        sess["user_name"] = test_user["name"]
    return client


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def count_expenses(user_id):
    """Return the number of expense rows for a given user_id."""
    conn = sqlite3.connect(db_module.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    count = conn.execute(
        "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()
    return count


def fetch_last_expense(user_id):
    """Return the most recently inserted expense row for the given user, or None."""
    conn = sqlite3.connect(db_module.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    row = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


VALID_PAYLOAD = {
    "amount": "42.50",
    "category": "Food",
    "date": date.today().strftime("%Y-%m-%d"),
    "description": "Lunch at the canteen",
}


# ------------------------------------------------------------------ #
# Auth guard                                                          #
# ------------------------------------------------------------------ #

class TestAuthGuard:

    def test_unauthenticated_get_redirects_to_login(self, client):
        """Unauthenticated GET /expenses/add must redirect to /login."""
        response = client.get("/expenses/add", follow_redirects=False)
        assert response.status_code == 302, (
            f"Expected 302 redirect for unauthenticated GET /expenses/add, got {response.status_code}"
        )
        location = response.headers.get("Location", "")
        assert "login" in location, (
            f"Expected redirect to /login, got Location: {location}"
        )

    def test_unauthenticated_post_redirects_to_login(self, client):
        """Unauthenticated POST /expenses/add must redirect to /login."""
        response = client.post(
            "/expenses/add", data=VALID_PAYLOAD, follow_redirects=False
        )
        assert response.status_code == 302, (
            f"Expected 302 redirect for unauthenticated POST /expenses/add, got {response.status_code}"
        )
        location = response.headers.get("Location", "")
        assert "login" in location, (
            f"Expected redirect to /login, got Location: {location}"
        )

    def test_unauthenticated_get_following_redirect_reaches_login_page(self, client):
        """Following the redirect from unauthenticated GET should land on the login page."""
        response = client.get("/expenses/add", follow_redirects=True)
        assert response.status_code == 200, (
            "Following unauthenticated /expenses/add redirect should yield 200"
        )
        assert b"Login" in response.data or b"login" in response.data, (
            "Expected login page content after following unauthenticated /expenses/add redirect"
        )

    def test_unauthenticated_post_does_not_insert_row(self, client, test_user):
        """Unauthenticated POST must not insert any row into the expenses table."""
        before = count_expenses(test_user["id"])
        client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)
        after = count_expenses(test_user["id"])
        assert after == before, (
            "Unauthenticated POST must not insert an expense row"
        )


# ------------------------------------------------------------------ #
# GET — form rendering                                                #
# ------------------------------------------------------------------ #

class TestGetForm:

    def test_authenticated_get_returns_200(self, auth_client):
        """Authenticated GET /expenses/add must return HTTP 200."""
        response = auth_client.get("/expenses/add")
        assert response.status_code == 200, (
            f"Expected 200 for authenticated GET /expenses/add, got {response.status_code}"
        )

    def test_get_renders_amount_field(self, auth_client):
        """Form must contain an amount input field."""
        response = auth_client.get("/expenses/add")
        assert b'name="amount"' in response.data or b"name='amount'" in response.data, (
            "Expected <input name='amount'> in add expense form"
        )

    def test_get_renders_category_select(self, auth_client):
        """Form must contain a category select element."""
        response = auth_client.get("/expenses/add")
        assert b'name="category"' in response.data or b"name='category'" in response.data, (
            "Expected <select name='category'> in add expense form"
        )

    def test_get_renders_date_field(self, auth_client):
        """Form must contain a date input field."""
        response = auth_client.get("/expenses/add")
        assert b'name="date"' in response.data or b"name='date'" in response.data, (
            "Expected <input name='date'> in add expense form"
        )

    def test_get_renders_description_field(self, auth_client):
        """Form must contain an optional description field."""
        response = auth_client.get("/expenses/add")
        assert b'name="description"' in response.data or b"name='description'" in response.data, (
            "Expected <input name='description'> in add expense form"
        )

    def test_get_renders_submit_button(self, auth_client):
        """Form must contain an 'Add Expense' submit button."""
        response = auth_client.get("/expenses/add")
        assert b"Add Expense" in response.data, (
            "Expected 'Add Expense' submit button in the add expense form"
        )

    def test_get_contains_all_seven_categories(self, auth_client):
        """Category select must contain all seven whitelisted options."""
        categories = [b"Food", b"Transport", b"Bills", b"Health",
                      b"Entertainment", b"Shopping", b"Other"]
        response = auth_client.get("/expenses/add")
        for cat in categories:
            assert cat in response.data, (
                f"Expected category option '{cat.decode()}' in the category select"
            )

    def test_get_todays_date_prefilled(self, auth_client):
        """Date field must be pre-filled with today's date in YYYY-MM-DD format."""
        today = date.today().strftime("%Y-%m-%d").encode()
        response = auth_client.get("/expenses/add")
        assert today in response.data, (
            f"Expected today's date '{today.decode()}' to be pre-filled in the date field"
        )

    def test_get_extends_base_template(self, auth_client):
        """Add expense page must use the shared base layout."""
        response = auth_client.get("/expenses/add")
        assert b"Spendly" in response.data, (
            "Expected 'Spendly' branding from base.html in the add expense page"
        )

    def test_get_has_cancel_link_to_profile(self, auth_client):
        """Form must contain a cancel link that points back to /profile."""
        response = auth_client.get("/expenses/add")
        assert b"/profile" in response.data, (
            "Expected a cancel link pointing to /profile in the add expense form"
        )

    def test_get_form_method_is_post(self, auth_client):
        """Form element must use method='POST'."""
        response = auth_client.get("/expenses/add")
        assert b'method="post"' in response.data.lower() or b"method='post'" in response.data.lower(), (
            "Expected form method='POST' in add expense form"
        )


# ------------------------------------------------------------------ #
# POST — happy path                                                   #
# ------------------------------------------------------------------ #

class TestPostHappyPath:

    def test_valid_post_redirects_to_profile(self, auth_client):
        """Valid POST /expenses/add must redirect to /profile."""
        response = auth_client.post(
            "/expenses/add", data=VALID_PAYLOAD, follow_redirects=False
        )
        assert response.status_code == 302, (
            f"Expected 302 redirect after successful expense insert, got {response.status_code}"
        )
        location = response.headers.get("Location", "")
        assert "profile" in location, (
            f"Expected redirect to /profile after successful insert, got Location: {location}"
        )

    def test_valid_post_inserts_one_row(self, auth_client, test_user):
        """Valid POST must insert exactly one row in the expenses table."""
        before = count_expenses(test_user["id"])
        auth_client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)
        after = count_expenses(test_user["id"])
        assert after == before + 1, (
            f"Expected exactly one new expense row, but count went from {before} to {after}"
        )

    def test_valid_post_stores_correct_amount(self, auth_client, test_user):
        """Inserted expense must store the correct amount."""
        auth_client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)
        expense = fetch_last_expense(test_user["id"])
        assert expense is not None, "Expected an expense row to be inserted"
        assert float(expense["amount"]) == pytest.approx(42.50), (
            f"Expected amount 42.50, got {expense['amount']}"
        )

    def test_valid_post_stores_correct_category(self, auth_client, test_user):
        """Inserted expense must store the correct category."""
        auth_client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)
        expense = fetch_last_expense(test_user["id"])
        assert expense is not None, "Expected an expense row to be inserted"
        assert expense["category"] == "Food", (
            f"Expected category 'Food', got '{expense['category']}'"
        )

    def test_valid_post_stores_correct_date(self, auth_client, test_user):
        """Inserted expense must store the correct date string."""
        today_str = date.today().strftime("%Y-%m-%d")
        auth_client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)
        expense = fetch_last_expense(test_user["id"])
        assert expense is not None, "Expected an expense row to be inserted"
        assert expense["date"] == today_str, (
            f"Expected date '{today_str}', got '{expense['date']}'"
        )

    def test_valid_post_stores_correct_description(self, auth_client, test_user):
        """Inserted expense must store the provided description."""
        auth_client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)
        expense = fetch_last_expense(test_user["id"])
        assert expense is not None, "Expected an expense row to be inserted"
        assert expense["description"] == "Lunch at the canteen", (
            f"Expected description 'Lunch at the canteen', got '{expense['description']}'"
        )

    def test_valid_post_flash_message_on_success(self, auth_client):
        """After a successful POST, following the redirect must show a success flash message."""
        response = auth_client.post(
            "/expenses/add", data=VALID_PAYLOAD, follow_redirects=True
        )
        assert response.status_code == 200, (
            "Following successful POST redirect should yield 200"
        )
        assert b"Expense added successfully" in response.data, (
            "Expected 'Expense added successfully' flash message after successful insert"
        )

    def test_valid_post_expense_appears_on_profile(self, auth_client):
        """After a successful insert, the expense amount must appear on the /profile page."""
        auth_client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)
        profile_response = auth_client.get("/profile")
        assert b"42" in profile_response.data or b"42.50" in profile_response.data, (
            "Newly inserted expense (42.50) must appear in the /profile transaction list"
        )


# ------------------------------------------------------------------ #
# POST — user_id comes from session, never from form                  #
# ------------------------------------------------------------------ #

class TestUserIdFromSession:

    def test_inserted_expense_user_id_matches_session(self, auth_client, test_user):
        """Expense user_id must match the session user_id, not any form-supplied value."""
        # Attempt to supply a different user_id via form data — it must be ignored
        payload = dict(VALID_PAYLOAD, user_id="999")
        auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        expense = fetch_last_expense(test_user["id"])
        assert expense is not None, "Expected an expense row to be inserted"
        assert expense["user_id"] == test_user["id"], (
            f"Expected user_id={test_user['id']} from session, "
            f"but got user_id={expense['user_id']}"
        )

    def test_second_user_cannot_read_first_users_expense(self, client, app):
        """A different logged-in user must not see another user's expense on /profile."""
        from werkzeug.security import generate_password_hash

        # Create two users
        conn = sqlite3.connect(db_module.DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("User One", "one@spendly.com", generate_password_hash("pass1234")),
        )
        conn.commit()
        user1_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("User Two", "two@spendly.com", generate_password_hash("pass5678")),
        )
        conn.commit()
        user2_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()

        # Log in as user 1 and add an expense with a distinctive amount
        with client.session_transaction() as sess:
            sess["user_id"] = user1_id
            sess["user_name"] = "User One"
        payload = dict(VALID_PAYLOAD, amount="999.99", description="User One secret expense")
        client.post("/expenses/add", data=payload, follow_redirects=False)

        # Switch session to user 2
        with client.session_transaction() as sess:
            sess["user_id"] = user2_id
            sess["user_name"] = "User Two"

        profile_response = client.get("/profile")
        assert b"User One secret expense" not in profile_response.data, (
            "User Two must not see User One's expense description on their profile"
        )


# ------------------------------------------------------------------ #
# POST — description optional                                         #
# ------------------------------------------------------------------ #

class TestDescriptionOptional:

    def test_post_without_description_field_succeeds(self, auth_client, test_user):
        """Valid POST omitting the description field entirely must succeed."""
        payload = {
            "amount": "15.00",
            "category": "Transport",
            "date": date.today().strftime("%Y-%m-%d"),
            # description key absent
        }
        response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        assert response.status_code == 302, (
            f"Expected 302 redirect when description is absent, got {response.status_code}"
        )
        assert count_expenses(test_user["id"]) == 1, (
            "Expected exactly one expense row when description is absent"
        )

    def test_post_with_empty_description_succeeds(self, auth_client, test_user):
        """Valid POST with an empty description string must succeed."""
        payload = {
            "amount": "15.00",
            "category": "Transport",
            "date": date.today().strftime("%Y-%m-%d"),
            "description": "",
        }
        response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        assert response.status_code == 302, (
            f"Expected 302 redirect when description is empty, got {response.status_code}"
        )
        assert count_expenses(test_user["id"]) == 1, (
            "Expected exactly one expense row when description is empty string"
        )

    def test_post_empty_description_stores_none_or_empty(self, auth_client, test_user):
        """Empty description must be stored as NULL or empty string — not raise an error."""
        payload = {
            "amount": "15.00",
            "category": "Transport",
            "date": date.today().strftime("%Y-%m-%d"),
            "description": "",
        }
        auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        expense = fetch_last_expense(test_user["id"])
        assert expense is not None, "Expected an expense row"
        # description should be None (NULL) or empty string — either is acceptable
        assert expense["description"] is None or expense["description"] == "", (
            f"Empty description should be stored as NULL or empty, got '{expense['description']}'"
        )


# ------------------------------------------------------------------ #
# POST — validation failures                                          #
# ------------------------------------------------------------------ #

class TestValidationAmount:

    @pytest.mark.parametrize("bad_amount,label", [
        ("0",      "zero"),
        ("0.00",   "zero as decimal"),
        ("-5",     "negative integer"),
        ("-0.01",  "negative decimal"),
        ("",       "empty string"),
        ("   ",    "whitespace only"),
        ("abc",    "non-numeric string"),
        ("1e999",  "overflow float string"),
    ])
    def test_invalid_amount_returns_200(self, auth_client, bad_amount, label):
        """Invalid amount must return 200 (re-render the form), not a redirect."""
        payload = dict(VALID_PAYLOAD, amount=bad_amount)
        response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        assert response.status_code == 200, (
            f"Expected 200 for amount='{label}', got {response.status_code}"
        )

    @pytest.mark.parametrize("bad_amount,label", [
        ("0",      "zero"),
        ("-5",     "negative integer"),
        ("",       "empty string"),
        ("abc",    "non-numeric string"),
    ])
    def test_invalid_amount_shows_error_message(self, auth_client, bad_amount, label):
        """Invalid amount must render an error message in the response."""
        payload = dict(VALID_PAYLOAD, amount=bad_amount)
        response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        assert b"error" in response.data.lower() or b"Amount" in response.data or b"positive" in response.data, (
            f"Expected an error message for amount='{label}', none found in response"
        )

    @pytest.mark.parametrize("bad_amount,label", [
        ("0",      "zero"),
        ("-5",     "negative integer"),
        ("",       "empty string"),
        ("abc",    "non-numeric string"),
    ])
    def test_invalid_amount_does_not_insert_row(self, auth_client, test_user, bad_amount, label):
        """Invalid amount must not insert any row into the expenses table."""
        before = count_expenses(test_user["id"])
        payload = dict(VALID_PAYLOAD, amount=bad_amount)
        auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        after = count_expenses(test_user["id"])
        assert after == before, (
            f"Expected no DB insert for amount='{label}', but count changed from {before} to {after}"
        )


class TestValidationCategory:

    @pytest.mark.parametrize("bad_category,label", [
        ("",              "empty string"),
        ("Groceries",     "similar but not whitelisted"),
        ("food",          "wrong case"),
        ("FOOD",          "all caps"),
        ("<script>",      "XSS attempt"),
        ("' OR '1'='1",  "SQL injection"),
        ("InvalidCat",    "arbitrary string"),
    ])
    def test_invalid_category_returns_200(self, auth_client, bad_category, label):
        """Category not in the whitelist must return 200 (form re-render)."""
        payload = dict(VALID_PAYLOAD, category=bad_category)
        response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        assert response.status_code == 200, (
            f"Expected 200 for category='{label}', got {response.status_code}"
        )

    @pytest.mark.parametrize("bad_category,label", [
        ("",           "empty string"),
        ("Groceries",  "similar but not whitelisted"),
        ("food",       "wrong case"),
    ])
    def test_invalid_category_shows_error_message(self, auth_client, bad_category, label):
        """Invalid category must render an error message."""
        payload = dict(VALID_PAYLOAD, category=bad_category)
        response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        assert b"error" in response.data.lower() or b"category" in response.data.lower(), (
            f"Expected an error message for category='{label}', none found"
        )

    @pytest.mark.parametrize("bad_category,label", [
        ("",           "empty string"),
        ("Groceries",  "not whitelisted"),
        ("food",       "wrong case"),
    ])
    def test_invalid_category_does_not_insert_row(self, auth_client, test_user, bad_category, label):
        """Invalid category must not insert any row into the expenses table."""
        before = count_expenses(test_user["id"])
        payload = dict(VALID_PAYLOAD, category=bad_category)
        auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        after = count_expenses(test_user["id"])
        assert after == before, (
            f"Expected no DB insert for category='{label}', count went from {before} to {after}"
        )

    def test_all_whitelisted_categories_accepted(self, auth_client, test_user):
        """Each of the seven whitelisted categories must be accepted as valid."""
        categories = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]
        for cat in categories:
            payload = {
                "amount": "10.00",
                "category": cat,
                "date": date.today().strftime("%Y-%m-%d"),
                "description": f"Test for {cat}",
            }
            response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
            assert response.status_code == 302, (
                f"Expected 302 redirect for whitelisted category '{cat}', got {response.status_code}"
            )


class TestValidationDate:

    @pytest.mark.parametrize("bad_date,label", [
        ("",             "empty string"),
        ("   ",          "whitespace only"),
        ("31-08-2026",   "DD-MM-YYYY format"),
        ("08/31/2026",   "MM/DD/YYYY format"),
        ("2026-13-01",   "month out of range"),
        ("not-a-date",   "arbitrary string"),
        ("2026-08",      "partial date"),
    ])
    def test_invalid_date_returns_200(self, auth_client, bad_date, label):
        """Missing or malformed date must return 200 (form re-render)."""
        payload = dict(VALID_PAYLOAD, date=bad_date)
        response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        assert response.status_code == 200, (
            f"Expected 200 for date='{label}', got {response.status_code}"
        )

    @pytest.mark.parametrize("bad_date,label", [
        ("",           "empty string"),
        ("not-a-date", "arbitrary string"),
        ("31-08-2026", "wrong format"),
    ])
    def test_invalid_date_shows_error_message(self, auth_client, bad_date, label):
        """Invalid date must render an error message."""
        payload = dict(VALID_PAYLOAD, date=bad_date)
        response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        assert b"error" in response.data.lower() or b"date" in response.data.lower(), (
            f"Expected an error message for date='{label}', none found"
        )

    @pytest.mark.parametrize("bad_date,label", [
        ("",           "empty string"),
        ("not-a-date", "arbitrary string"),
        ("31-08-2026", "wrong format"),
    ])
    def test_invalid_date_does_not_insert_row(self, auth_client, test_user, bad_date, label):
        """Invalid date must not insert any row into the expenses table."""
        before = count_expenses(test_user["id"])
        payload = dict(VALID_PAYLOAD, date=bad_date)
        auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        after = count_expenses(test_user["id"])
        assert after == before, (
            f"Expected no DB insert for date='{label}', count went from {before} to {after}"
        )

    def test_missing_date_field_entirely_returns_200(self, auth_client):
        """POST with no date key in form data must return 200 (form re-render)."""
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "date"}
        response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        assert response.status_code == 200, (
            f"Expected 200 when date field is absent from POST data, got {response.status_code}"
        )


# ------------------------------------------------------------------ #
# POST — form persistence on validation failure                       #
# ------------------------------------------------------------------ #

class TestFormPersistenceOnFailure:

    def test_amount_persisted_after_invalid_category(self, auth_client):
        """After category validation failure, previously entered amount must appear in response."""
        payload = {
            "amount": "77.77",
            "category": "NotACategory",
            "date": date.today().strftime("%Y-%m-%d"),
            "description": "Persisted description",
        }
        response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        assert b"77.77" in response.data or b"77" in response.data, (
            "Expected amount '77.77' to be re-populated in the form after category validation failure"
        )

    def test_description_persisted_after_invalid_amount(self, auth_client):
        """After amount validation failure, previously entered description must appear in response."""
        payload = {
            "amount": "0",
            "category": "Food",
            "date": date.today().strftime("%Y-%m-%d"),
            "description": "My unique description XYZ",
        }
        response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        assert b"My unique description XYZ" in response.data, (
            "Expected description to be re-populated in form after amount=0 validation failure"
        )

    def test_category_persisted_after_invalid_date(self, auth_client):
        """After date validation failure, previously selected category must appear in response."""
        payload = {
            "amount": "50.00",
            "category": "Health",
            "date": "not-a-date",
            "description": "",
        }
        response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        assert b"Health" in response.data, (
            "Expected category 'Health' to be re-populated in form after date validation failure"
        )

    def test_date_persisted_after_invalid_amount(self, auth_client):
        """After amount validation failure, previously entered date must appear in response."""
        specific_date = "2026-07-15"
        payload = {
            "amount": "-100",
            "category": "Bills",
            "date": specific_date,
            "description": "",
        }
        response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        assert specific_date.encode() in response.data, (
            f"Expected date '{specific_date}' to be re-populated in form after negative amount failure"
        )

    def test_all_fields_persisted_after_invalid_category(self, auth_client):
        """After any validation failure, all entered fields must be re-populated."""
        specific_date = "2026-09-20"
        payload = {
            "amount": "123.45",
            "category": "BadCategory",
            "date": specific_date,
            "description": "Persist all fields",
        }
        response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        assert b"123" in response.data, "Amount not persisted"
        assert specific_date.encode() in response.data, "Date not persisted"
        assert b"Persist all fields" in response.data, "Description not persisted"


# ------------------------------------------------------------------ #
# POST — edge cases                                                   #
# ------------------------------------------------------------------ #

class TestEdgeCases:

    def test_very_long_description_does_not_crash(self, auth_client, test_user):
        """A description longer than 200 characters must not crash the app."""
        long_desc = "A" * 500
        payload = dict(VALID_PAYLOAD, description=long_desc)
        response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        # Spec says truncate or reject — either is acceptable; must not 500
        assert response.status_code in (200, 302), (
            f"Expected 200 or 302 for overlong description, got {response.status_code}"
        )
        assert b"Internal Server Error" not in response.data, (
            "Long description must not cause a 500 error page"
        )

    def test_sql_injection_in_description_stored_safely(self, auth_client, test_user):
        """SQL injection in description must be stored safely via parameterized query."""
        malicious = "'; DROP TABLE expenses; --"
        payload = dict(VALID_PAYLOAD, amount="5.00", description=malicious)
        response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        assert response.status_code == 302, (
            "SQL injection in description should not prevent a successful insert"
        )
        # Verify expenses table still exists and has the row
        expense = fetch_last_expense(test_user["id"])
        assert expense is not None, (
            "expenses table must still exist and contain the row after SQL injection attempt"
        )

    def test_amount_with_many_decimal_places_accepted_or_rejected_gracefully(self, auth_client, test_user):
        """Amount with excessive decimal places must not crash the server."""
        payload = dict(VALID_PAYLOAD, amount="10.123456789")
        response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        # Route converts to float — this should succeed and redirect
        assert response.status_code in (200, 302), (
            f"Unexpected status for high-precision amount: {response.status_code}"
        )
        assert b"Internal Server Error" not in response.data, (
            "High-precision amount must not cause a server error"
        )

    def test_valid_past_date_accepted(self, auth_client, test_user):
        """A valid date in the past must be accepted."""
        payload = dict(VALID_PAYLOAD, date="2020-01-15")
        response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        assert response.status_code == 302, (
            "Past date '2020-01-15' must be accepted and result in a 302 redirect"
        )

    def test_valid_future_date_accepted(self, auth_client, test_user):
        """A valid date in the future must be accepted (spec imposes no restriction)."""
        payload = dict(VALID_PAYLOAD, date="2030-12-31")
        response = auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        assert response.status_code == 302, (
            "Future date '2030-12-31' must be accepted and result in a 302 redirect"
        )

    def test_multiple_sequential_expenses_all_inserted(self, auth_client, test_user):
        """Submitting the form multiple times must create a separate row each time."""
        for i in range(3):
            payload = dict(VALID_PAYLOAD, amount=f"{10 + i}.00", description=f"Expense {i}")
            auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        assert count_expenses(test_user["id"]) == 3, (
            "Three sequential valid POSTs must create exactly three expense rows"
        )

    def test_whitespace_only_description_stored_as_empty_or_none(self, auth_client, test_user):
        """Whitespace-only description must be stripped and stored as NULL or empty."""
        payload = dict(VALID_PAYLOAD, description="   ")
        auth_client.post("/expenses/add", data=payload, follow_redirects=False)
        expense = fetch_last_expense(test_user["id"])
        assert expense is not None, "Expected an expense row to be inserted"
        stored = expense["description"]
        assert stored is None or stored == "" or stored.strip() == "", (
            f"Whitespace description should be stored as empty/NULL, got '{stored}'"
        )
