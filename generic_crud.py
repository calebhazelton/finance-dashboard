"""
Generic CRUD logic shared across all tables.

Table and column names can't be parameterized with '?' placeholders in SQLite,
so we whitelist every table name and look up real column names via
PRAGMA table_info before building any query. Only VALUES ever come from
user input, and those are always passed as parameters, never string-formatted
into the SQL. This is what keeps this safe from SQL injection despite the
dynamic table/column handling.
"""

import sqlite3
from database import get_db

# Every table the API is allowed to touch. Add new tables here as you add
# them to schema.sql -- nothing works unless it's listed.
ALLOWED_TABLES = {
    "income_sources",
    "income_actuals",
    "expense_categories",
    "expense_actuals",
    "debts",
    "debt_payment_log",
    "investment_accounts",
    "investment_contribution_log",
    "net_worth_snapshots",
}


class InvalidTable(Exception):
    pass


class InvalidColumn(Exception):
    pass


def _check_table(table):
    if table not in ALLOWED_TABLES:
        raise InvalidTable(f"'{table}' is not a recognized table")


def get_columns(table):
    """Return the real column names for a table, straight from SQLite."""
    _check_table(table)
    db = get_db()
    rows = db.execute(f"PRAGMA table_info({table})").fetchall()
    return [row["name"] for row in rows]


def _filter_to_known_columns(table, data):
    """Drop any keys the caller sent that aren't real columns (defense in depth)."""
    columns = set(get_columns(table))
    return {k: v for k, v in data.items() if k in columns and k != "id"}


def list_rows(table, filters=None):
    _check_table(table)
    db = get_db()
    query = f"SELECT * FROM {table}"
    params = []
    if filters:
        clean = _filter_to_known_columns(table, filters)
        if clean:
            where = " AND ".join(f"{col} = ?" for col in clean)
            query += f" WHERE {where}"
            params = list(clean.values())
    rows = db.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_row(table, row_id):
    _check_table(table)
    db = get_db()
    row = db.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
    return dict(row) if row else None


def create_row(table, data):
    _check_table(table)
    clean = _filter_to_known_columns(table, data)
    if not clean:
        raise InvalidColumn("No valid columns provided")
    db = get_db()
    cols = ", ".join(clean.keys())
    placeholders = ", ".join("?" for _ in clean)
    cursor = db.execute(
        f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
        list(clean.values()),
    )
    db.commit()
    return get_row(table, cursor.lastrowid)


def update_row(table, row_id, data):
    _check_table(table)
    clean = _filter_to_known_columns(table, data)
    if not clean:
        raise InvalidColumn("No valid columns provided")
    db = get_db()
    set_clause = ", ".join(f"{col} = ?" for col in clean)
    params = list(clean.values()) + [row_id]
    db.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", params)
    db.commit()
    return get_row(table, row_id)


def delete_row(table, row_id):
    _check_table(table)
    db = get_db()
    db.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
    db.commit()
