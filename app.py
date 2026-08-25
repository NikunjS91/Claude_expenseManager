from datetime import datetime, timedelta, date

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from database.db import get_db, init_db, seed_db
from database.queries import (
    get_user_by_id, get_summary_stats,
    get_recent_transactions, get_category_breakdown,
)

app = Flask(__name__)
app.secret_key = "spendly-dev-secret"  # TODO: move to env var before production


def parse_date(val):
    try:
        datetime.strptime(val, "%Y-%m-%d")
        return val
    except (ValueError, TypeError):
        return None

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

    uid = session["user_id"]
    user = get_user_by_id(uid)
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    today     = date.today()
    today_str = today.strftime("%Y-%m-%d")

    date_from = parse_date(request.args.get("date_from", ""))
    date_to   = parse_date(request.args.get("date_to", ""))

    if bool(date_from) != bool(date_to):
        flash("Please provide both a start and end date.", "error")
        date_from = date_to = None
    elif date_from and date_to and date_from > date_to:
        flash("Start date must be before end date.", "error")
        date_from = date_to = None

    first_of_month   = today.replace(day=1).strftime("%Y-%m-%d")
    three_months_ago = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    six_months_ago   = (today - timedelta(days=180)).strftime("%Y-%m-%d")

    preset_dates = {
        "this_month": {"date_from": first_of_month,   "date_to": today_str},
        "3m":         {"date_from": three_months_ago,  "date_to": today_str},
        "6m":         {"date_from": six_months_ago,    "date_to": today_str},
    }

    if date_from is None and date_to is None:
        active_preset = "all"
    elif date_from == first_of_month and date_to == today_str:
        active_preset = "this_month"
    elif date_from == three_months_ago and date_to == today_str:
        active_preset = "3m"
    elif date_from == six_months_ago and date_to == today_str:
        active_preset = "6m"
    else:
        active_preset = "custom"

    stats        = get_summary_stats(uid, date_from=date_from, date_to=date_to)
    transactions = get_recent_transactions(uid, limit=10, date_from=date_from, date_to=date_to)
    categories   = get_category_breakdown(uid, date_from=date_from, date_to=date_to)

    return render_template("profile.html",
        user=user, stats=stats,
        transactions=transactions, categories=categories,
        date_from=date_from or "", date_to=date_to or "",
        active_preset=active_preset,
        preset_dates=preset_dates,
    )


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
