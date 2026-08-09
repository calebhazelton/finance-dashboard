"""
Production entry point. waitress-serve needs a plain module-level `app`
object to import -- it can't call create_app() itself the way python3
app.py's __main__ block does. This file just does that one call.
"""
from app import create_app

app = create_app()
