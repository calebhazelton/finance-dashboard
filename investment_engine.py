"""
Investment growth projection engine.

Also computed live from whatever's currently in investment_accounts --
nothing here is persisted, so results always reflect current balances
and contribution settings on the next page load.
"""


def estimate_monthly_contribution(account, income_sources_by_id):
    """Employee + employer monthly contribution, estimated from the linked income source."""
    source = income_sources_by_id.get(account.get("linked_income_source_id"))
    if not source:
        return 0.0
    gross_monthly = source["expected_gross_monthly"]
    employee_pct = account.get("contribution_percent") or 0.0
    match_pct = account.get("employer_match_percent") or 0.0
    return gross_monthly * (employee_pct + match_pct)


def project_growth(accounts, income_sources_by_id, months=120):
    """
    Compounds each account monthly at its expected_annual_return, adding
    its estimated monthly contribution each period.

    Returns per-account projected balances plus a yearly combined-balance
    schedule (one point per 12 months) for a compact table.
    """
    balances = {a["id"]: a["current_balance"] for a in accounts}
    monthly_contribs = {a["id"]: estimate_monthly_contribution(a, income_sources_by_id) for a in accounts}

    schedule = []
    for m in range(1, months + 1):
        for a in accounts:
            aid = a["id"]
            monthly_rate = (a.get("expected_annual_return") or 0.0) / 12
            balances[aid] = balances[aid] * (1 + monthly_rate) + monthly_contribs[aid]
        if m % 12 == 0 or m == months:
            schedule.append({
                "month": m,
                "years": round(m / 12, 1),
                "total_balance": sum(balances.values()),
            })

    per_account = {
        a["id"]: {
            "monthly_contribution": monthly_contribs[a["id"]],
            "projected_balance": balances[a["id"]],
        }
        for a in accounts
    }

    return {
        "per_account": per_account,
        "schedule": schedule,
        "total_current_balance": sum(a["current_balance"] for a in accounts),
        "total_monthly_contribution": sum(monthly_contribs.values()),
        "total_projected_balance": sum(balances.values()),
    }
