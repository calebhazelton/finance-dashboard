from datetime import date

def current_month():
    """Return the current month as 'YYYY-MM', matching the format stored in the DB."""
    return date.today().strftime("%Y-%m")
