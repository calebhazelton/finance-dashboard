from datetime import date

def current_month():
    """Return the current month as 'YYYY-MM', matching the format stored in the DB."""
    return date.today().strftime("%Y-%m")


# Multiplier to convert an amount at a given billing frequency into its
# monthly equivalent, e.g. an annual $1200 bill is $100/month.
FREQUENCY_TO_MONTHLY_FACTOR = {
    "weekly": 52 / 12,
    "biweekly": 26 / 12,
    "monthly": 1,
    "semiannually": 2 / 12,
    "annually": 1 / 12,
}

FREQUENCY_LABELS = {
    "weekly": "Weekly",
    "biweekly": "Biweekly",
    "monthly": "Monthly",
    "semiannually": "Semiannually",
    "annually": "Annually",
}


def monthly_equivalent(amount, frequency):
    """Convert `amount` billed at `frequency` into its monthly equivalent."""
    factor = FREQUENCY_TO_MONTHLY_FACTOR.get(frequency, 1)
    return amount * factor


def hourly_to_expected_gross_monthly(hourly_rate, hours_per_week):
    """Standard conversion: rate * hours/week * 52 weeks/year / 12 months/year."""
    return hourly_rate * hours_per_week * 52 / 12
