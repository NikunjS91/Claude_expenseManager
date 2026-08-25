from database.db import get_db


def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    conn = get_db()
    try:
        if date_from and date_to:
            rows = conn.execute(
                "SELECT date, description, category, amount FROM expenses "
                "WHERE user_id = ? AND date BETWEEN ? AND ? ORDER BY date DESC LIMIT ?",
                (user_id, date_from, date_to, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT date, description, category, amount FROM expenses "
                "WHERE user_id = ? ORDER BY date DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
    finally:
        conn.close()
    return [
        {
            "date": row["date"],
            "description": row["description"],
            "category": row["category"],
            "amount": f"₹{row['amount']:,.2f}",
        }
        for row in rows
    ]
