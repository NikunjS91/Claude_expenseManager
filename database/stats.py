from database.db import get_db


def get_summary_stats(user_id, date_from=None, date_to=None):
    conn = get_db()
    try:
        if date_from and date_to:
            rows = conn.execute(
                "SELECT amount, category FROM expenses "
                "WHERE user_id = ? AND date BETWEEN ? AND ?",
                (user_id, date_from, date_to)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT amount, category FROM expenses WHERE user_id = ?",
                (user_id,)
            ).fetchall()
    finally:
        conn.close()

    count = len(rows)

    if count == 0:
        return {"total": "₹0.00", "count": 0, "top_cat": "—"}

    total = sum(row["amount"] for row in rows)

    category_totals = {}
    for row in rows:
        cat = row["category"]
        category_totals[cat] = category_totals.get(cat, 0) + row["amount"]
    top_cat = max(category_totals, key=category_totals.get)

    return {
        "total": f"₹{total:,.2f}",
        "count": count,
        "top_cat": top_cat,
    }
