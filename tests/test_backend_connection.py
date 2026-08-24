import pytest
from werkzeug.security import generate_password_hash

import app as flask_app
from database.db import get_db
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_test_user():
    """Remove any test users created during a test."""
    yield
    conn = get_db()
    conn.execute("DELETE FROM expenses WHERE user_id IN (SELECT id FROM users WHERE email = 'test@example.com')")
    conn.execute("DELETE FROM users WHERE email = 'test@example.com'")
    conn.commit()
    conn.close()


def _insert_test_user():
    conn = get_db()
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Test User", "test@example.com", generate_password_hash("password")),
    )
    conn.commit()
    uid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return uid


def _insert_test_expenses(user_id):
    expenses = [
        (user_id, 500.0,  "Food",     "2026-08-01", "Groceries"),
        (user_id, 200.0,  "Transport","2026-08-02", "Metro"),
        (user_id, 300.0,  "Food",     "2026-08-03", "Dinner"),
    ]
    conn = get_db()
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?,?,?,?,?)",
        expenses,
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# get_user_by_id
# ---------------------------------------------------------------------------

def test_get_user_by_id_valid():
    uid = _insert_test_user()
    user = get_user_by_id(uid)
    assert user is not None
    assert user["name"] == "Test User"
    assert user["email"] == "test@example.com"
    assert user["created_at"]  # formatted "Month YYYY"


def test_get_user_by_id_missing():
    assert get_user_by_id(999999) is None


# ---------------------------------------------------------------------------
# get_summary_stats
# ---------------------------------------------------------------------------

def test_get_summary_stats_with_expenses():
    uid = _insert_test_user()
    _insert_test_expenses(uid)
    stats = get_summary_stats(uid)
    assert stats["count"] == 3
    assert stats["total"] == "₹1,000.00"
    assert stats["top_cat"] == "Food"  # 500+300=800 > Transport 200


def test_get_summary_stats_no_expenses():
    uid = _insert_test_user()
    stats = get_summary_stats(uid)
    assert stats == {"total": "₹0.00", "count": 0, "top_cat": "—"}


# ---------------------------------------------------------------------------
# get_recent_transactions
# ---------------------------------------------------------------------------

def test_get_recent_transactions_with_expenses():
    uid = _insert_test_user()
    _insert_test_expenses(uid)
    txs = get_recent_transactions(uid)
    assert len(txs) == 3
    # newest first
    assert txs[0]["date"] == "2026-08-03"
    assert txs[-1]["date"] == "2026-08-01"
    for tx in txs:
        assert "date" in tx
        assert "description" in tx
        assert "category" in tx
        assert tx["amount"].startswith("₹")


def test_get_recent_transactions_no_expenses():
    uid = _insert_test_user()
    assert get_recent_transactions(uid) == []


def test_get_recent_transactions_limit():
    uid = _insert_test_user()
    _insert_test_expenses(uid)
    txs = get_recent_transactions(uid, limit=2)
    assert len(txs) == 2


# ---------------------------------------------------------------------------
# get_category_breakdown
# ---------------------------------------------------------------------------

def test_get_category_breakdown_with_expenses():
    uid = _insert_test_user()
    _insert_test_expenses(uid)
    cats = get_category_breakdown(uid)
    assert len(cats) == 2  # Food and Transport
    # sorted by total desc — Food (800) first
    assert cats[0]["name"] == "Food"
    pcts = [c["pct"] for c in cats]
    assert sum(pcts) == 100
    for cat in cats:
        assert cat["total"].startswith("₹")
        assert isinstance(cat["pct"], int)


def test_get_category_breakdown_no_expenses():
    uid = _insert_test_user()
    assert get_category_breakdown(uid) == []


# ---------------------------------------------------------------------------
# Route: GET /profile
# ---------------------------------------------------------------------------

def test_profile_unauthenticated(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_profile_authenticated(client):
    # Use the seeded demo user
    conn = get_db()
    demo = conn.execute("SELECT id, name FROM users WHERE email = 'demo@spendly.com'").fetchone()
    conn.close()

    with client.session_transaction() as sess:
        sess["user_id"] = demo["id"]
        sess["user_name"] = demo["name"]

    response = client.get("/profile")
    assert response.status_code == 200
    body = response.data.decode()
    assert "Demo User" in body
    assert "demo@spendly.com" in body
    assert "₹" in body
