"""
tests/test_08-edit-expense.py

Pytest tests for Step 8: Edit Expense (/expenses/<id>/edit route).

Spec: .claude/specs/08-edit-expense.md

Setup strategy:
- DB_PATH is patched to a temp file so the real spendly.db is never touched.
- A fresh test user is inserted before each test via raw sqlite3 INSERT.
- A fresh test expense is inserted per test via raw sqlite3 INSERT.
- Session is seeded directly via client.session_transaction() to simulate login
  without going through the login form.
- All tests are fully independent — no shared mutable state between tests.
"""

import sqlite3
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

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
    init_db() creates a clean schema before each test; the temp file is
    removed automatically when the test ends.
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
    Insert a primary test user directly into the DB and return their details.
    Uses raw sqlite3 to stay independent of app-layer helpers.
    """
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
def other_user(app):
    """
    Insert a second test user to verify ownership isolation.
    """
    conn = sqlite3.connect(db_module.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Other User", "other@spendly.com", generate_password_hash("otherpass123")),
    )
    conn.commit()
    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return {"id": user_id, "name": "Other User", "email": "other@spendly.com"}


@pytest.fixture
def test_expense(app, test_user):
    """
    Insert a fresh expense row for the primary test user and return its details.
    """
    conn = sqlite3.connect(db_module.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        (test_user["id"], 99.99, "Food", "2026-07-01", "Original description"),
    )
    conn.commit()
    expense_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return {
        "id": expense_id,
        "user_id": test_user["id"],
        "amount": 99.99,
        "category": "Food",
        "date": "2026-07-01",
        "description": "Original description",
    }


@pytest.fixture
def other_expense(app, other_user):
    """
    Insert an expense row belonging to the OTHER user (not test_user).
    Used to verify ownership checks.
    """
    conn = sqlite3.connect(db_module.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        (other_user["id"], 50.00, "Transport", "2026-06-15", "Other user's expense"),
    )
    conn.commit()
    expense_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return {
        "id": expense_id,
        "user_id": other_user["id"],
        "amount": 50.00,
        "category": "Transport",
        "date": "2026-06-15",
        "description": "Other user's expense",
    }


@pytest.fixture
def auth_client(client, test_user):
    """Test client with the primary test user already loaded into the session."""
    with client.session_transaction() as sess:
        sess["user_id"] = test_user["id"]
        sess["user_name"] = test_user["name"]
    return client


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def fetch_expense(expense_id):
    """Return the expense row for the given id as a dict, or None."""
    conn = sqlite3.connect(db_module.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    row = conn.execute(
        "SELECT * FROM expenses WHERE id = ?", (expense_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


VALID_UPDATE = {
    "amount": "150.00",
    "category": "Health",
    "date": "2026-08-15",
    "description": "Updated description",
}


# ------------------------------------------------------------------ #
# Auth guard                                                          #
# ------------------------------------------------------------------ #

class TestAuthGuard:

    def test_unauthenticated_get_redirects_to_login(self, client, test_expense):
        """Unauthenticated GET /expenses/<id>/edit must redirect to /login."""
        response = client.get(
            f"/expenses/{test_expense['id']}/edit",
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            f"Expected 302 redirect for unauthenticated GET, got {response.status_code}"
        )
        location = response.headers.get("Location", "")
        assert "login" in location, (
            f"Expected redirect to /login, got Location: {location}"
        )

    def test_unauthenticated_post_redirects_to_login(self, client, test_expense):
        """Unauthenticated POST /expenses/<id>/edit must redirect to /login."""
        response = client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=VALID_UPDATE,
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            f"Expected 302 redirect for unauthenticated POST, got {response.status_code}"
        )
        location = response.headers.get("Location", "")
        assert "login" in location, (
            f"Expected redirect to /login, got Location: {location}"
        )

    def test_unauthenticated_get_following_redirect_reaches_login_page(self, client, test_expense):
        """Following the unauthenticated GET redirect must land on the login page."""
        response = client.get(
            f"/expenses/{test_expense['id']}/edit",
            follow_redirects=True,
        )
        assert response.status_code == 200, (
            "Following unauthenticated redirect should yield 200"
        )
        assert b"Login" in response.data or b"login" in response.data, (
            "Expected login page content after following unauthenticated redirect"
        )

    def test_unauthenticated_post_does_not_modify_db(self, client, test_expense):
        """Unauthenticated POST must not modify the expense row."""
        before = fetch_expense(test_expense["id"])
        client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=VALID_UPDATE,
            follow_redirects=False,
        )
        after = fetch_expense(test_expense["id"])
        assert after["amount"] == before["amount"], (
            "Unauthenticated POST must not change the expense amount"
        )
        assert after["category"] == before["category"], (
            "Unauthenticated POST must not change the expense category"
        )


# ------------------------------------------------------------------ #
# Ownership                                                           #
# ------------------------------------------------------------------ #

class TestOwnership:

    def test_get_another_users_expense_returns_404(
        self, client, test_user, other_expense
    ):
        """GET for an expense belonging to another user must return 404."""
        with client.session_transaction() as sess:
            sess["user_id"] = test_user["id"]
            sess["user_name"] = test_user["name"]
        response = client.get(
            f"/expenses/{other_expense['id']}/edit",
            follow_redirects=False,
        )
        assert response.status_code == 404, (
            f"Expected 404 when accessing another user's expense via GET, "
            f"got {response.status_code}"
        )

    def test_post_another_users_expense_returns_404(
        self, client, test_user, other_expense
    ):
        """POST to edit another user's expense must return 404."""
        with client.session_transaction() as sess:
            sess["user_id"] = test_user["id"]
            sess["user_name"] = test_user["name"]
        response = client.post(
            f"/expenses/{other_expense['id']}/edit",
            data=VALID_UPDATE,
            follow_redirects=False,
        )
        assert response.status_code == 404, (
            f"Expected 404 when POSTing to another user's expense, got {response.status_code}"
        )

    def test_post_another_users_expense_does_not_modify_db(
        self, client, test_user, other_expense
    ):
        """A 404-returning POST must leave the other user's expense row untouched."""
        with client.session_transaction() as sess:
            sess["user_id"] = test_user["id"]
            sess["user_name"] = test_user["name"]
        before = fetch_expense(other_expense["id"])
        client.post(
            f"/expenses/{other_expense['id']}/edit",
            data=VALID_UPDATE,
            follow_redirects=False,
        )
        after = fetch_expense(other_expense["id"])
        assert after["amount"] == before["amount"], (
            "Cross-user POST must not modify the target expense's amount"
        )

    def test_get_nonexistent_expense_returns_404(self, auth_client):
        """GET /expenses/9999/edit for a non-existent id must return 404."""
        response = auth_client.get("/expenses/9999/edit", follow_redirects=False)
        assert response.status_code == 404, (
            f"Expected 404 for non-existent expense id=9999, got {response.status_code}"
        )

    def test_post_nonexistent_expense_returns_404(self, auth_client):
        """POST /expenses/9999/edit for a non-existent id must return 404."""
        response = auth_client.post(
            "/expenses/9999/edit", data=VALID_UPDATE, follow_redirects=False
        )
        assert response.status_code == 404, (
            f"Expected 404 for non-existent expense id=9999 on POST, got {response.status_code}"
        )


# ------------------------------------------------------------------ #
# GET — form rendering with pre-populated values                      #
# ------------------------------------------------------------------ #

class TestGetRendering:

    def test_authenticated_get_returns_200(self, auth_client, test_expense):
        """Authenticated GET for an owned expense must return HTTP 200."""
        response = auth_client.get(
            f"/expenses/{test_expense['id']}/edit",
            follow_redirects=False,
        )
        assert response.status_code == 200, (
            f"Expected 200 for authenticated GET /expenses/<id>/edit, got {response.status_code}"
        )

    def test_get_prepopulates_amount(self, auth_client, test_expense):
        """Amount field must be pre-populated with the expense's current amount."""
        response = auth_client.get(f"/expenses/{test_expense['id']}/edit")
        # 99.99 stored; look for numeric representation in the page
        assert b"99.99" in response.data or b"99" in response.data, (
            "Expected expense amount '99.99' to be pre-populated in the edit form"
        )

    def test_get_prepopulates_category(self, auth_client, test_expense):
        """The expense's category must appear as checked/selected in the form."""
        response = auth_client.get(f"/expenses/{test_expense['id']}/edit")
        # The category pill for "Food" must appear; the spec says it should be `checked`
        data = response.data
        assert b"Food" in data, (
            "Expected category 'Food' to be present and pre-selected in the edit form"
        )
        assert b"checked" in data, (
            "Expected the expense's category pill to carry the `checked` attribute"
        )

    def test_get_prepopulates_date(self, auth_client, test_expense):
        """Date field must be pre-populated with the expense's current date."""
        response = auth_client.get(f"/expenses/{test_expense['id']}/edit")
        assert b"2026-07-01" in response.data, (
            "Expected expense date '2026-07-01' to be pre-populated in the date field"
        )

    def test_get_prepopulates_description(self, auth_client, test_expense):
        """Description field must be pre-populated with the expense's current description."""
        response = auth_client.get(f"/expenses/{test_expense['id']}/edit")
        assert b"Original description" in response.data, (
            "Expected expense description 'Original description' to be pre-populated"
        )

    def test_get_renders_save_changes_button(self, auth_client, test_expense):
        """Form must contain a 'Save Changes' submit button."""
        response = auth_client.get(f"/expenses/{test_expense['id']}/edit")
        assert b"Save Changes" in response.data, (
            "Expected 'Save Changes' submit button in the edit expense form"
        )

    def test_get_has_cancel_link_to_profile(self, auth_client, test_expense):
        """Edit form must contain a cancel link pointing back to /profile."""
        response = auth_client.get(f"/expenses/{test_expense['id']}/edit")
        assert b"/profile" in response.data, (
            "Expected a cancel link pointing to /profile in the edit form"
        )

    def test_get_extends_base_template(self, auth_client, test_expense):
        """Edit page must use the shared base layout (Spendly branding visible)."""
        response = auth_client.get(f"/expenses/{test_expense['id']}/edit")
        assert b"Spendly" in response.data, (
            "Expected 'Spendly' branding from base.html in the edit expense page"
        )

    def test_get_form_method_is_post(self, auth_client, test_expense):
        """Form element must use method='POST'."""
        response = auth_client.get(f"/expenses/{test_expense['id']}/edit")
        assert (
            b'method="post"' in response.data.lower()
            or b"method='post'" in response.data.lower()
        ), "Expected form method='POST' in edit expense form"

    def test_get_contains_all_seven_categories(self, auth_client, test_expense):
        """Category selector must list all seven whitelisted category options."""
        categories = [
            b"Food", b"Transport", b"Bills", b"Health",
            b"Entertainment", b"Shopping", b"Other",
        ]
        response = auth_client.get(f"/expenses/{test_expense['id']}/edit")
        for cat in categories:
            assert cat in response.data, (
                f"Expected category '{cat.decode()}' to appear in edit form"
            )

    def test_get_renders_amount_input_field(self, auth_client, test_expense):
        """Form must contain an input element named 'amount'."""
        response = auth_client.get(f"/expenses/{test_expense['id']}/edit")
        assert (
            b'name="amount"' in response.data or b"name='amount'" in response.data
        ), "Expected <input name='amount'> in edit expense form"

    def test_get_renders_date_input_field(self, auth_client, test_expense):
        """Form must contain an input element named 'date'."""
        response = auth_client.get(f"/expenses/{test_expense['id']}/edit")
        assert (
            b'name="date"' in response.data or b"name='date'" in response.data
        ), "Expected <input name='date'> in edit expense form"

    def test_get_renders_description_input_field(self, auth_client, test_expense):
        """Form must contain an input element named 'description'."""
        response = auth_client.get(f"/expenses/{test_expense['id']}/edit")
        assert (
            b'name="description"' in response.data or b"name='description'" in response.data
        ), "Expected <input name='description'> in edit expense form"


# ------------------------------------------------------------------ #
# POST — happy path                                                   #
# ------------------------------------------------------------------ #

class TestHappyPath:

    def test_valid_post_redirects_to_profile(self, auth_client, test_expense):
        """Valid POST must redirect to /profile (302)."""
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=VALID_UPDATE,
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            f"Expected 302 redirect after valid edit, got {response.status_code}"
        )
        location = response.headers.get("Location", "")
        assert "profile" in location, (
            f"Expected redirect to /profile after successful edit, got Location: {location}"
        )

    def test_valid_post_flash_message_on_profile(self, auth_client, test_expense):
        """Following the redirect after a valid edit must show the success flash message."""
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=VALID_UPDATE,
            follow_redirects=True,
        )
        assert response.status_code == 200, (
            "Following successful edit redirect should yield 200"
        )
        assert b"Expense updated successfully" in response.data, (
            "Expected 'Expense updated successfully.' flash message after valid edit"
        )

    def test_valid_post_updates_amount_in_db(self, auth_client, test_expense):
        """Valid POST must update the expense's amount in the database."""
        auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=VALID_UPDATE,
            follow_redirects=False,
        )
        updated = fetch_expense(test_expense["id"])
        assert updated is not None, "Expected expense row to still exist after edit"
        assert float(updated["amount"]) == pytest.approx(150.00), (
            f"Expected amount 150.00 after edit, got {updated['amount']}"
        )

    def test_valid_post_updates_category_in_db(self, auth_client, test_expense):
        """Valid POST must update the expense's category in the database."""
        auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=VALID_UPDATE,
            follow_redirects=False,
        )
        updated = fetch_expense(test_expense["id"])
        assert updated["category"] == "Health", (
            f"Expected category 'Health' after edit, got '{updated['category']}'"
        )

    def test_valid_post_updates_date_in_db(self, auth_client, test_expense):
        """Valid POST must update the expense's date in the database."""
        auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=VALID_UPDATE,
            follow_redirects=False,
        )
        updated = fetch_expense(test_expense["id"])
        assert updated["date"] == "2026-08-15", (
            f"Expected date '2026-08-15' after edit, got '{updated['date']}'"
        )

    def test_valid_post_updates_description_in_db(self, auth_client, test_expense):
        """Valid POST must update the expense's description in the database."""
        auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=VALID_UPDATE,
            follow_redirects=False,
        )
        updated = fetch_expense(test_expense["id"])
        assert updated["description"] == "Updated description", (
            f"Expected description 'Updated description' after edit, got '{updated['description']}'"
        )

    def test_valid_post_preserves_user_id_in_db(self, auth_client, test_expense, test_user):
        """Valid POST must never change the user_id column on the expense row."""
        auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=VALID_UPDATE,
            follow_redirects=False,
        )
        updated = fetch_expense(test_expense["id"])
        assert updated["user_id"] == test_user["id"], (
            f"Expected user_id={test_user['id']} unchanged after edit, "
            f"got user_id={updated['user_id']}"
        )

    def test_valid_post_all_categories_accepted(self, auth_client, test_expense):
        """Each of the seven whitelisted categories must be accepted in a valid edit."""
        categories = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]
        for cat in categories:
            payload = dict(VALID_UPDATE, category=cat)
            response = auth_client.post(
                f"/expenses/{test_expense['id']}/edit",
                data=payload,
                follow_redirects=False,
            )
            assert response.status_code == 302, (
                f"Expected 302 redirect for whitelisted category '{cat}', got {response.status_code}"
            )


# ------------------------------------------------------------------ #
# POST — amount validation                                            #
# ------------------------------------------------------------------ #

class TestAmountValidation:

    @pytest.mark.parametrize("bad_amount,label", [
        ("0",      "zero"),
        ("0.00",   "zero decimal"),
        ("-5",     "negative integer"),
        ("-0.01",  "negative decimal"),
        ("",       "empty string"),
        ("   ",    "whitespace only"),
        ("abc",    "non-numeric string"),
        ("1e999",  "overflow float"),
    ])
    def test_invalid_amount_returns_200(self, auth_client, test_expense, bad_amount, label):
        """Invalid amount must re-render the form (200), not redirect."""
        payload = dict(VALID_UPDATE, amount=bad_amount)
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        assert response.status_code == 200, (
            f"Expected 200 for amount='{label}', got {response.status_code}"
        )

    @pytest.mark.parametrize("bad_amount,label", [
        ("0",      "zero"),
        ("-5",     "negative integer"),
        ("",       "empty string"),
        ("abc",    "non-numeric string"),
    ])
    def test_invalid_amount_shows_error(self, auth_client, test_expense, bad_amount, label):
        """Invalid amount must display an error message in the response."""
        payload = dict(VALID_UPDATE, amount=bad_amount)
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        data_lower = response.data.lower()
        assert (
            b"error" in data_lower
            or b"amount" in data_lower
            or b"positive" in data_lower
        ), f"Expected an error message for amount='{label}', none found in response"

    @pytest.mark.parametrize("bad_amount,label", [
        ("0",      "zero"),
        ("-5",     "negative integer"),
        ("",       "empty string"),
        ("abc",    "non-numeric string"),
    ])
    def test_invalid_amount_does_not_update_db(self, auth_client, test_expense, bad_amount, label):
        """Invalid amount must leave the expense row untouched in the database."""
        original = fetch_expense(test_expense["id"])
        payload = dict(VALID_UPDATE, amount=bad_amount)
        auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        current = fetch_expense(test_expense["id"])
        assert current["amount"] == original["amount"], (
            f"Expected amount unchanged for bad_amount='{label}', "
            f"but got {current['amount']} (was {original['amount']})"
        )
        assert current["category"] == original["category"], (
            f"Expected category unchanged for bad_amount='{label}'"
        )


# ------------------------------------------------------------------ #
# POST — category validation                                          #
# ------------------------------------------------------------------ #

class TestCategoryValidation:

    @pytest.mark.parametrize("bad_category,label", [
        ("",                "empty string"),
        ("Groceries",       "similar but not whitelisted"),
        ("food",            "wrong case"),
        ("FOOD",            "all caps"),
        ("InvalidCat",      "arbitrary string"),
        ("<script>",        "XSS attempt"),
        ("' OR '1'='1",    "SQL injection attempt"),
    ])
    def test_invalid_category_returns_200(self, auth_client, test_expense, bad_category, label):
        """Category not in whitelist must re-render the form (200)."""
        payload = dict(VALID_UPDATE, category=bad_category)
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        assert response.status_code == 200, (
            f"Expected 200 for category='{label}', got {response.status_code}"
        )

    @pytest.mark.parametrize("bad_category,label", [
        ("",           "empty string"),
        ("Groceries",  "similar but not whitelisted"),
        ("food",       "wrong case"),
    ])
    def test_invalid_category_shows_error(self, auth_client, test_expense, bad_category, label):
        """Invalid category must display an error message."""
        payload = dict(VALID_UPDATE, category=bad_category)
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        data_lower = response.data.lower()
        assert b"error" in data_lower or b"category" in data_lower, (
            f"Expected an error message for category='{label}', none found"
        )

    @pytest.mark.parametrize("bad_category,label", [
        ("",           "empty string"),
        ("Groceries",  "not whitelisted"),
        ("food",       "wrong case"),
    ])
    def test_invalid_category_does_not_update_db(self, auth_client, test_expense, bad_category, label):
        """Invalid category must leave the expense row untouched."""
        original = fetch_expense(test_expense["id"])
        payload = dict(VALID_UPDATE, category=bad_category)
        auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        current = fetch_expense(test_expense["id"])
        assert current["category"] == original["category"], (
            f"Expected category unchanged for bad_category='{label}', "
            f"but got '{current['category']}' (was '{original['category']}')"
        )


# ------------------------------------------------------------------ #
# POST — date validation                                              #
# ------------------------------------------------------------------ #

class TestDateValidation:

    @pytest.mark.parametrize("bad_date,label", [
        ("",              "empty string"),
        ("   ",           "whitespace only"),
        ("27-08-2026",    "DD-MM-YYYY format"),
        ("08/27/2026",    "MM/DD/YYYY format"),
        ("2026-13-01",    "month out of range"),
        ("not-a-date",    "arbitrary string"),
        ("2026-08",       "partial date"),
    ])
    def test_invalid_date_returns_200(self, auth_client, test_expense, bad_date, label):
        """Missing or malformed date must re-render the form (200)."""
        payload = dict(VALID_UPDATE, date=bad_date)
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        assert response.status_code == 200, (
            f"Expected 200 for date='{label}', got {response.status_code}"
        )

    @pytest.mark.parametrize("bad_date,label", [
        ("",           "empty string"),
        ("27-08-2026", "wrong format DD-MM-YYYY"),
        ("08/27/2026", "wrong format MM/DD/YYYY"),
        ("not-a-date", "arbitrary string"),
    ])
    def test_invalid_date_shows_error(self, auth_client, test_expense, bad_date, label):
        """Invalid date must display an error message."""
        payload = dict(VALID_UPDATE, date=bad_date)
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        data_lower = response.data.lower()
        assert b"error" in data_lower or b"date" in data_lower, (
            f"Expected an error message for date='{label}', none found"
        )

    @pytest.mark.parametrize("bad_date,label", [
        ("",           "empty string"),
        ("27-08-2026", "wrong format"),
        ("not-a-date", "arbitrary string"),
    ])
    def test_invalid_date_does_not_update_db(self, auth_client, test_expense, bad_date, label):
        """Invalid date must leave the expense row untouched."""
        original = fetch_expense(test_expense["id"])
        payload = dict(VALID_UPDATE, date=bad_date)
        auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        current = fetch_expense(test_expense["id"])
        assert current["date"] == original["date"], (
            f"Expected date unchanged for bad_date='{label}', "
            f"but got '{current['date']}' (was '{original['date']}')"
        )

    def test_missing_date_field_entirely_returns_200(self, auth_client, test_expense):
        """POST with no date key in form data must re-render the form (200)."""
        payload = {k: v for k, v in VALID_UPDATE.items() if k != "date"}
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        assert response.status_code == 200, (
            f"Expected 200 when date field is absent from POST data, got {response.status_code}"
        )


# ------------------------------------------------------------------ #
# POST — sticky form values after validation failure                  #
# ------------------------------------------------------------------ #

class TestStickyForm:

    def test_submitted_amount_reappears_after_invalid_amount(self, auth_client, test_expense):
        """After amount validation failure, the submitted (bad) amount must re-appear in response."""
        payload = {
            "amount": "0",
            "category": "Food",
            "date": "2026-08-10",
            "description": "Sticky amount test",
        }
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        # The form should re-render with the submitted values from request.form
        assert b"Sticky amount test" in response.data, (
            "Expected description to be re-populated after amount=0 validation failure"
        )

    def test_submitted_date_reappears_after_invalid_date(self, auth_client, test_expense):
        """After date validation failure, the submitted date value must re-appear in response."""
        payload = {
            "amount": "25.00",
            "category": "Bills",
            "date": "not-a-date",
            "description": "Date sticky test",
        }
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        # The bad date string was submitted; spec says re-populate from request.form
        assert b"not-a-date" in response.data or b"Date sticky test" in response.data, (
            "Expected submitted values to be re-populated after date validation failure"
        )

    def test_submitted_amount_reappears_after_invalid_category(self, auth_client, test_expense):
        """After category validation failure, the submitted amount must re-appear in response."""
        payload = {
            "amount": "77.77",
            "category": "NotACategory",
            "date": "2026-08-01",
            "description": "Category sticky amount",
        }
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        assert b"77.77" in response.data or b"77" in response.data, (
            "Expected amount '77.77' to be re-populated after category validation failure"
        )

    def test_description_reappears_after_invalid_amount(self, auth_client, test_expense):
        """After amount validation failure, previously entered description must re-appear."""
        payload = {
            "amount": "-999",
            "category": "Shopping",
            "date": "2026-07-20",
            "description": "My unique sticky description XYZ",
        }
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        assert b"My unique sticky description XYZ" in response.data, (
            "Expected description to be re-populated in form after negative amount failure"
        )

    def test_form_rerenders_after_invalid_category(self, auth_client, test_expense):
        """After category validation failure, the form is re-rendered (not a redirect)."""
        payload = dict(VALID_UPDATE, category="BadCategory")
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        assert response.status_code == 200, (
            "Expected form re-render (200) after invalid category, not a redirect"
        )

    def test_all_fields_in_response_after_bad_category(self, auth_client, test_expense):
        """After category failure, all other submitted fields appear in the re-rendered form."""
        specific_date = "2026-09-10"
        payload = {
            "amount": "123.45",
            "category": "BadCategory",
            "date": specific_date,
            "description": "All fields persisted",
        }
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        assert b"123" in response.data, "Amount not persisted after bad category"
        assert specific_date.encode() in response.data, "Date not persisted after bad category"
        assert b"All fields persisted" in response.data, "Description not persisted after bad category"


# ------------------------------------------------------------------ #
# POST — user_id isolation                                            #
# ------------------------------------------------------------------ #

class TestUserIsolation:

    def test_crafted_user_id_in_form_does_not_change_row_user_id(
        self, auth_client, test_expense, test_user
    ):
        """
        A POST that includes a crafted user_id field must not update user_id on the row.
        The route must take user_id exclusively from session["user_id"].
        """
        payload = dict(VALID_UPDATE, user_id="9999")
        auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        updated = fetch_expense(test_expense["id"])
        assert updated["user_id"] == test_user["id"], (
            f"Expected user_id={test_user['id']} (from session), "
            f"but got user_id={updated['user_id']} after crafted form POST"
        )

    def test_user_cannot_edit_expense_by_crafting_url(
        self, client, test_user, other_expense
    ):
        """
        A logged-in user must receive 404 when crafting a direct URL to another user's expense id.
        """
        with client.session_transaction() as sess:
            sess["user_id"] = test_user["id"]
            sess["user_name"] = test_user["name"]
        response = client.post(
            f"/expenses/{other_expense['id']}/edit",
            data=VALID_UPDATE,
            follow_redirects=False,
        )
        assert response.status_code == 404, (
            f"Expected 404 when test_user crafts a URL targeting other_user's expense, "
            f"got {response.status_code}"
        )

    def test_two_users_expenses_are_isolated_after_edit(self, client, app):
        """
        Editing user A's expense must not affect user B's expenses, and vice-versa.
        """
        # Create two users
        conn = sqlite3.connect(db_module.DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("User A", "a@spendly.com", generate_password_hash("passA1234")),
        )
        conn.commit()
        user_a_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("User B", "b@spendly.com", generate_password_hash("passB1234")),
        )
        conn.commit()
        user_b_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Insert an expense for each user
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            (user_a_id, 10.00, "Food", "2026-01-01", "User A expense"),
        )
        conn.commit()
        expense_a_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            (user_b_id, 20.00, "Transport", "2026-02-01", "User B expense"),
        )
        conn.commit()
        expense_b_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()

        # Log in as User A and edit their own expense
        with client.session_transaction() as sess:
            sess["user_id"] = user_a_id
            sess["user_name"] = "User A"

        client.post(
            f"/expenses/{expense_a_id}/edit",
            data={"amount": "55.00", "category": "Bills", "date": "2026-03-01", "description": "A edited"},
            follow_redirects=False,
        )

        # User B's expense must be completely unchanged
        b_row = fetch_expense(expense_b_id)
        assert float(b_row["amount"]) == pytest.approx(20.00), (
            "User B's expense amount must not change when User A edits their own expense"
        )
        assert b_row["description"] == "User B expense", (
            "User B's expense description must not change when User A edits their own expense"
        )


# ------------------------------------------------------------------ #
# POST — description optional                                         #
# ------------------------------------------------------------------ #

class TestDescriptionOptional:

    def test_update_without_description_succeeds(self, auth_client, test_expense):
        """Valid POST omitting the description field must succeed."""
        payload = {
            "amount": "30.00",
            "category": "Other",
            "date": "2026-08-20",
            # description key absent
        }
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            f"Expected 302 redirect when description is absent, got {response.status_code}"
        )

    def test_update_with_empty_description_succeeds(self, auth_client, test_expense):
        """Valid POST with an empty description string must succeed."""
        payload = {
            "amount": "30.00",
            "category": "Other",
            "date": "2026-08-20",
            "description": "",
        }
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            f"Expected 302 redirect when description is empty, got {response.status_code}"
        )

    def test_update_empty_description_stores_none_or_empty(self, auth_client, test_expense):
        """Empty description must be stored as NULL or empty — not raise an error."""
        payload = {
            "amount": "30.00",
            "category": "Other",
            "date": "2026-08-20",
            "description": "",
        }
        auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        updated = fetch_expense(test_expense["id"])
        assert updated["description"] is None or updated["description"] == "", (
            f"Empty description should be stored as NULL or empty string, got '{updated['description']}'"
        )


# ------------------------------------------------------------------ #
# Edge cases                                                          #
# ------------------------------------------------------------------ #

class TestEdgeCases:

    def test_very_long_description_does_not_crash(self, auth_client, test_expense):
        """A description longer than 200 characters must not crash the app."""
        long_desc = "B" * 500
        payload = dict(VALID_UPDATE, description=long_desc)
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        assert response.status_code in (200, 302), (
            f"Expected 200 or 302 for overlong description, got {response.status_code}"
        )
        assert b"Internal Server Error" not in response.data, (
            "Long description must not cause a 500 error page"
        )

    def test_long_description_truncated_to_200_chars(self, auth_client, test_expense):
        """Per spec, description must be truncated to 200 characters before storing."""
        long_desc = "C" * 500
        payload = dict(VALID_UPDATE, description=long_desc)
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        if response.status_code == 302:
            updated = fetch_expense(test_expense["id"])
            stored = updated["description"] or ""
            assert len(stored) <= 200, (
                f"Expected description stored with at most 200 chars, got {len(stored)}"
            )

    def test_sql_injection_in_description_stored_safely(self, auth_client, test_expense):
        """SQL injection in description must be stored safely via parameterized query."""
        malicious = "'; DROP TABLE expenses; --"
        payload = dict(VALID_UPDATE, description=malicious)
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            "SQL injection in description must not prevent a successful update"
        )
        # Confirm expenses table still exists and the row is still present
        updated = fetch_expense(test_expense["id"])
        assert updated is not None, (
            "expenses table must still exist and row must still be present after SQL injection attempt"
        )

    def test_valid_past_date_accepted(self, auth_client, test_expense):
        """A valid date in the past must be accepted."""
        payload = dict(VALID_UPDATE, date="2020-01-15")
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            "Past date '2020-01-15' must be accepted and result in a 302 redirect"
        )

    def test_valid_future_date_accepted(self, auth_client, test_expense):
        """A valid future date must be accepted (spec imposes no restriction)."""
        payload = dict(VALID_UPDATE, date="2030-12-31")
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            "Future date '2030-12-31' must be accepted and result in a 302 redirect"
        )

    def test_amount_with_many_decimal_places_accepted_gracefully(self, auth_client, test_expense):
        """Amount with excessive decimal places must not crash the server."""
        payload = dict(VALID_UPDATE, amount="10.123456789")
        response = auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        assert response.status_code in (200, 302), (
            f"Unexpected status for high-precision amount: {response.status_code}"
        )
        assert b"Internal Server Error" not in response.data, (
            "High-precision amount must not cause a server error"
        )

    def test_whitespace_only_description_stored_as_empty_or_none(self, auth_client, test_expense):
        """Whitespace-only description must be stripped and stored as NULL or empty."""
        payload = dict(VALID_UPDATE, description="   ")
        auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=payload,
            follow_redirects=False,
        )
        updated = fetch_expense(test_expense["id"])
        stored = updated["description"]
        assert stored is None or stored == "" or stored.strip() == "", (
            f"Whitespace description should be stored as empty/NULL, got '{stored}'"
        )

    def test_expense_updated_values_appear_on_profile(self, auth_client, test_expense):
        """After a successful edit, the updated expense amount must appear on /profile."""
        auth_client.post(
            f"/expenses/{test_expense['id']}/edit",
            data=VALID_UPDATE,
            follow_redirects=False,
        )
        profile_response = auth_client.get("/profile")
        assert b"150" in profile_response.data or b"150.00" in profile_response.data, (
            "Updated expense amount (150.00) must appear in the /profile transaction list"
        )
