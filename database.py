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

def register_app(app):
    """Wire up teardown so connections close after each request."""
    app.teardown_appcontext(close_db)
