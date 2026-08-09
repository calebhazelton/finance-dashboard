"""
Debt payoff projection engine (avalanche / snowball).

Nothing here is stored in the database. Every call recalculates from
whatever's currently in the `debts` table, so numbers are always live --
update a balance on the Debts page and the projection reflects it
immediately on the next page load.
"""

from datetime import date

MAX_MONTHS = 600  # safety cap (50 years) so a bad input can't loop forever


def _add_months(start_date, n):
    month_index = start_date.month - 1 + n
    year = start_date.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def simulate_payoff(debts, extra_monthly=0.0, strategy="avalanche"):
    """
    debts: list of dicts with keys id, name, current_balance, apr, min_payment
    strategy: 'avalanche' (highest APR first) or 'snowball' (smallest balance first)

    Returns:
      order: debts sorted by payoff priority
      per_debt: {id: {"payoff_month": int|None, "payoff_date": str|None}}
      schedule: [{"month": int, "date": "YYYY-MM", "total_balance": float}, ...]
      months_to_payoff, payoff_date, total_interest_paid
    """
    if not debts:
        return {
            "order": [], "per_debt": {}, "schedule": [],
            "months_to_payoff": 0, "payoff_date": None, "total_interest_paid": 0.0,
        }

    if strategy == "snowball":
        order = sorted(debts, key=lambda d: d["current_balance"])
    else:
        order = sorted(debts, key=lambda d: -d["apr"])

    balances = {d["id"]: d["current_balance"] for d in debts}
    min_payments = {d["id"]: d["min_payment"] for d in debts}
    aprs = {d["id"]: d["apr"] for d in debts}

    per_debt_payoff_month = {}
    schedule = []
    total_interest_paid = 0.0
    start = date.today().replace(day=1)

    month_i = 0
    while any(b > 0.005 for b in balances.values()) and month_i < MAX_MONTHS:
        month_i += 1
        freed_up = 0.0  # minimum payments from already-paid-off debts roll into the priority debt

        for d in order:
            did = d["id"]
            if balances[did] <= 0:
                freed_up += min_payments[did]
                continue
            interest = balances[did] * (aprs[did] / 12)
            total_interest_paid += interest
            balances[did] += interest
            pay = min(min_payments[did], balances[did])
            balances[did] -= pay
            if balances[did] <= 0.005:
                per_debt_payoff_month[did] = month_i

        available_extra = extra_monthly + freed_up
        for d in order:
            did = d["id"]
            if balances[did] <= 0.005 or available_extra <= 0:
                continue
            pay = min(available_extra, balances[did])
            balances[did] -= pay
            available_extra -= pay
            if balances[did] <= 0.005:
                per_debt_payoff_month[did] = month_i

        total_balance = sum(max(b, 0) for b in balances.values())
        schedule.append({
            "month": month_i,
            "date": _add_months(start, month_i - 1).strftime("%Y-%m"),
            "total_balance": total_balance,
        })

    months_to_payoff = month_i if month_i < MAX_MONTHS else None
    payoff_date = (
        _add_months(start, months_to_payoff - 1).strftime("%B %Y") if months_to_payoff else None
    )

    per_debt = {}
    for d in order:
        pm = per_debt_payoff_month.get(d["id"])
        per_debt[d["id"]] = {
            "payoff_month": pm,
            "payoff_date": _add_months(start, pm - 1).strftime("%B %Y") if pm else None,
        }

    return {
        "order": order,
        "per_debt": per_debt,
        "schedule": schedule,
        "months_to_payoff": months_to_payoff,
        "payoff_date": payoff_date,
        "total_interest_paid": total_interest_paid,
    }
