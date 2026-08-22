from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)
app.secret_key = "spendly-dev-secret"  # TODO: move to env var before production

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("register.html")

    name     = request.form.get("name",     "").strip()
    email    = request.form.get("email",    "").strip()
    password = request.form.get("password", "").strip()

    if not name:
        return render_template("register.html", error="Name is required.")
    if not email:
        return render_template("register.html", error="Email is required.")
    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.")

    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        return render_template("register.html", error="An account with that email already exists.")

    password_hash = generate_password_hash(password)
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, password_hash),
    )
    conn.commit()
    new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()

    session["user_id"]   = new_id
    session["user_name"] = name
    flash("Account created successfully! Welcome to Spendly.", "success")
    return redirect(url_for("profile"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("login.html")

    email    = request.form.get("email",    "").strip()
    password = request.form.get("password", "").strip()

    if not email or not password:
        return render_template("login.html", error="Email and password are required.")

    conn = get_db()
    user = conn.execute(
        "SELECT id, name, password_hash FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()

    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session["user_id"]   = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = {
        "name":       "Nikunj Shetye",
        "email":      "nikunj@spendly.com",
        "created_at": "2026-01-15",
    }

    stats = {
        "total":   "₹4,600.00",
        "count":   8,
        "top_cat": "Shopping",
    }

    transactions = [
        {"date": "2026-08-18", "description": "Miscellaneous",    "category": "Other",         "amount": "₹100.00"},
        {"date": "2026-08-15", "description": "Restaurant dinner", "category": "Food",          "amount": "₹300.00"},
        {"date": "2026-08-12", "description": "Clothes",           "category": "Shopping",      "amount": "₹1,500.00"},
        {"date": "2026-08-10", "description": "Movie tickets",     "category": "Entertainment", "amount": "₹400.00"},
        {"date": "2026-08-08", "description": "Pharmacy",          "category": "Health",        "amount": "₹800.00"},
        {"date": "2026-08-05", "description": "Electricity bill",  "category": "Bills",         "amount": "₹1,200.00"},
        {"date": "2026-08-03", "description": "Metro pass",        "category": "Transport",     "amount": "₹50.00"},
        {"date": "2026-08-01", "description": "Groceries",         "category": "Food",          "amount": "₹250.00"},
    ]

    categories = [
        {"name": "Shopping",      "total": "₹1,500", "pct": 34},
        {"name": "Bills",         "total": "₹1,200", "pct": 27},
        {"name": "Health",        "total": "₹800",   "pct": 18},
        {"name": "Food",          "total": "₹550",   "pct": 13},
        {"name": "Entertainment", "total": "₹400",   "pct":  9},
        {"name": "Other",         "total": "₹100",   "pct":  2},
        {"name": "Transport",     "total": "₹50",    "pct":  1},
    ]

    return render_template("profile.html",
        user=user, stats=stats,
        transactions=transactions, categories=categories)


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


if __name__ == "__main__":
    app.run(debug=True, port=5001)
