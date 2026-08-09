import sqlite3
from pathlib import Path
from flask import g, current_app

def get_db():
    """Return a connection tied to the current request context."""
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE_PATH"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.row_factory = sqlite3.Row  # lets us access columns by name
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db(app):
    """Create tables from schema.sql if they don't exist yet."""
    db_path = Path(app.config["DATABASE_PATH"])
    db_path.parent.mkdir(parents=True, exist_ok=True)

    schema_path = Path(app.root_path) / "schema.sql"
    with sqlite3.connect(db_path) as conn:
        with open(schema_path, "r") as f:
            conn.executescript(f.read())
    print(f"Database initialized at {db_path}")

    run_migrations(app)


# Simple column-add migrations. CREATE TABLE IF NOT EXISTS (above) only
# helps for brand new databases -- an existing finance.db needs its
# tables altered in place. Each entry here is checked against the real
# schema and only applied if the column is missing, so this is safe to
# run every time the app starts, and safe to re-run after copying in a
# newer app.py without touching your data.
MIGRATIONS = [
    ("debts", "due_day", "INTEGER"),
    ("expense_categories", "due_day", "INTEGER"),
    ("income_sources", "pay_type", "TEXT NOT NULL DEFAULT 'salary'"),
    ("income_sources", "hourly_rate", "REAL"),
    ("income_sources", "hours_per_week", "REAL"),
    ("expense_categories", "frequency", "TEXT NOT NULL DEFAULT 'monthly'"),
]


def run_migrations(app):
    db_path = app.config["DATABASE_PATH"]
    with sqlite3.connect(db_path) as conn:
        for table, column, coltype in MIGRATIONS:
            existing_cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
            if column not in existing_cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
                print(f"Migrated: added {table}.{column}")
        conn.commit()

def register_app(app):
    """Wire up teardown so connections close after each request."""
    app.teardown_appcontext(close_db)
