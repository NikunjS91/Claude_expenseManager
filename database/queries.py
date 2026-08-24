from datetime import datetime

from database.db import get_db
from database.transactions import get_recent_transactions
from database.stats import get_summary_stats
from database.categories import get_category_breakdown


def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    dt = datetime.fromisoformat(row["created_at"])
    return {
        "name": row["name"],
        "email": row["email"],
        "created_at": dt.strftime("%B %Y"),
    }


__all__ = [
    "get_user_by_id",
    "get_summary_stats",
    "get_recent_transactions",
    "get_category_breakdown",
]
