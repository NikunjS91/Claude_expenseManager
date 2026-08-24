from database.db import get_db


def get_category_breakdown(user_id):
    conn = get_db()
    try:
        cursor = conn.execute(
            "SELECT category, SUM(amount) AS cat_total "
            "FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY cat_total DESC",
            (user_id,)
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    grand_total = sum(row["cat_total"] for row in rows)

    result = []
    for row in rows:
        pct = round(row["cat_total"] / grand_total * 100)
        result.append({
            "name": row["category"],
            "total": f"₹{row['cat_total']:,.0f}",
            "pct": pct,
            "_cat_total": row["cat_total"],
        })

    remainder = 100 - sum(item["pct"] for item in result)
    if result:
        result[0]["pct"] += remainder

    for item in result:
        del item["_cat_total"]

    return result
