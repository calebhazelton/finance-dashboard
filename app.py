from flask import Flask, jsonify, request, render_template, redirect, url_for, flash

import database
import generic_crud as crud
import helpers
import debt_engine
import investment_engine


def create_app():
    app = Flask(__name__)
    app.config["DATABASE_PATH"] = "instance/finance.db"
    # Only used to sign the flash-message cookie -- fine as-is for a LAN-only,
    # two-person household tool. Change it if you ever expose this beyond your network.
    app.config["SECRET_KEY"] = "dev-change-me"

    database.register_app(app)

    with app.app_context():
        database.init_db(app)

    # ---------- Dashboard ----------

    @app.route("/")
    def index():
        income_sources = crud.list_rows("income_sources")
        debts = crud.list_rows("debts")
        accounts = crud.list_rows("investment_accounts")
        categories = crud.list_rows("expense_categories")

        total_income_monthly = sum(
            s["expected_gross_monthly"] * (1 - s["effective_tax_rate"]) for s in income_sources
        )
        total_debt = sum(d["current_balance"] for d in debts)
        total_min_debt_payments = sum(d["min_payment"] for d in debts)
        total_investments = sum(a["current_balance"] for a in accounts)
        total_expenses_monthly = sum(
            helpers.monthly_equivalent(c["monthly_budget"], c.get("frequency") or "monthly")
            for c in categories
        )
        net_worth = total_investments - total_debt
        leftover = total_income_monthly - total_expenses_monthly - total_min_debt_payments

        return render_template(
            "base.html",
            net_worth=net_worth,
            total_debt=total_debt,
            total_investments=total_investments,
            total_income_monthly=total_income_monthly,
            total_expenses_monthly=total_expenses_monthly,
            leftover=leftover,
            debts=debts,
            accounts=accounts,
        )

    # ---------- Income page ----------

    @app.route("/income", methods=["GET"])
    def income_page():
        month = request.args.get("month") or helpers.current_month()
        sources = crud.list_rows("income_sources")
        actuals = crud.list_rows("income_actuals", {"month": month})

        expected_net_total = sum(
            s["expected_gross_monthly"] * (1 - s["effective_tax_rate"]) for s in sources
        )
        actual_net_total = sum(a["net_actual"] or 0 for a in actuals)

        return render_template(
            "income.html",
            sources=sources,
            actuals=actuals,
            month=month,
            expected_net_total=expected_net_total,
            actual_net_total=actual_net_total,
        )

    @app.route("/income/sources", methods=["POST"])
    def income_source_create():
        pay_type = request.form.get("pay_type", "salary").strip() or "salary"
        hourly_rate = request.form.get("hourly_rate", type=float)
        hours_per_week = request.form.get("hours_per_week", type=float)
        salary_input = request.form.get("expected_gross_monthly", type=float)

        if pay_type == "hourly":
            if hourly_rate is None or hours_per_week is None:
                flash("Please provide an hourly rate and hours per week.")
                return redirect(url_for("income_page"))
            expected_gross_monthly = helpers.hourly_to_expected_gross_monthly(hourly_rate, hours_per_week)
        else:
            if salary_input is None:
                flash("Please provide an expected gross monthly amount.")
                return redirect(url_for("income_page"))
            expected_gross_monthly = salary_input

        data = {
            "owner": request.form.get("owner", "").strip(),
            "name": request.form.get("name", "").strip(),
            "pay_frequency": request.form.get("pay_frequency", "").strip(),
            "pay_type": pay_type,
            "hourly_rate": hourly_rate,
            "hours_per_week": hours_per_week,
            "expected_gross_monthly": expected_gross_monthly,
            "effective_tax_rate": request.form.get("effective_tax_rate", type=float),
            "start_date": request.form.get("start_date") or None,
        }
        if not data["owner"] or not data["name"] or data["effective_tax_rate"] is None:
            flash("Please fill in owner, name, and tax rate.")
            return redirect(url_for("income_page"))
        crud.create_row("income_sources", data)
        flash(f"Added income source '{data['name']}'.")
        return redirect(url_for("income_page"))

    @app.route("/income/sources/<int:row_id>/delete", methods=["POST"])
    def income_source_delete(row_id):
        crud.delete_row("income_sources", row_id)
        flash("Income source deleted.")
        return redirect(url_for("income_page"))

    @app.route("/income/actuals", methods=["POST"])
    def income_actual_create():
        month = request.form.get("month", "").strip()
        data = {
            "income_source_id": request.form.get("income_source_id", type=int),
            "month": month,
            "gross_actual": request.form.get("gross_actual", type=float),
            "net_actual": request.form.get("net_actual", type=float),
        }
        if not data["income_source_id"] or not month:
            flash("Please select an income source and month.")
            return redirect(url_for("income_page"))
        crud.create_row("income_actuals", data)
        flash("Logged actual income.")
        return redirect(url_for("income_page", month=month))

    @app.route("/income/actuals/<int:row_id>/delete", methods=["POST"])
    def income_actual_delete(row_id):
        month = request.form.get("month")
        crud.delete_row("income_actuals", row_id)
        flash("Entry deleted.")
        return redirect(url_for("income_page", month=month))

    # ---------- Expenses page ----------

    @app.route("/expenses", methods=["GET"])
    def expenses_page():
        month = request.args.get("month") or helpers.current_month()
        categories = crud.list_rows("expense_categories")
        actuals = crud.list_rows("expense_actuals", {"month": month})

        actual_by_category = {}
        for a in actuals:
            actual_by_category[a["category_id"]] = actual_by_category.get(a["category_id"], 0) + a["amount_actual"]

        monthly_equiv_by_category = {
            c["id"]: helpers.monthly_equivalent(c["monthly_budget"], c.get("frequency") or "monthly")
            for c in categories
        }
        budget_total = sum(monthly_equiv_by_category.values())
        actual_total = sum(a["amount_actual"] for a in actuals)

        return render_template(
            "expenses.html",
            categories=categories,
            actuals=actuals,
            actual_by_category=actual_by_category,
            monthly_equiv_by_category=monthly_equiv_by_category,
            month=month,
            budget_total=budget_total,
            actual_total=actual_total,
            frequency_labels=helpers.FREQUENCY_LABELS,
        )

    @app.route("/expenses/categories", methods=["POST"])
    def expense_category_create():
        data = {
            "name": request.form.get("name", "").strip(),
            "monthly_budget": request.form.get("monthly_budget", type=float),
            "frequency": request.form.get("frequency", "monthly").strip() or "monthly",
            "due_day": request.form.get("due_day", type=int),
        }
        if not data["name"] or data["monthly_budget"] is None:
            flash("Please provide a category name and budget amount.")
            return redirect(url_for("expenses_page"))
        crud.create_row("expense_categories", data)
        flash(f"Added category '{data['name']}'.")
        return redirect(url_for("expenses_page"))

    @app.route("/expenses/categories/<int:row_id>/delete", methods=["POST"])
    def expense_category_delete(row_id):
        crud.delete_row("expense_categories", row_id)
        flash("Category deleted.")
        return redirect(url_for("expenses_page"))

    @app.route("/expenses/actuals", methods=["POST"])
    def expense_actual_create():
        month = request.form.get("month", "").strip()
        data = {
            "category_id": request.form.get("category_id", type=int),
            "month": month,
            "amount_actual": request.form.get("amount_actual", type=float),
        }
        if not data["category_id"] or not month or data["amount_actual"] is None:
            flash("Please select a category, month, and amount.")
            return redirect(url_for("expenses_page"))
        crud.create_row("expense_actuals", data)
        flash("Logged expense.")
        return redirect(url_for("expenses_page", month=month))

    @app.route("/expenses/actuals/<int:row_id>/delete", methods=["POST"])
    def expense_actual_delete(row_id):
        month = request.form.get("month")
        crud.delete_row("expense_actuals", row_id)
        flash("Entry deleted.")
        return redirect(url_for("expenses_page", month=month))

    # ---------- Debts page ----------

    @app.route("/debts", methods=["GET"])
    def debts_page():
        debts = crud.list_rows("debts")
        total_balance = sum(d["current_balance"] for d in debts)
        total_min_payment = sum(d["min_payment"] for d in debts)
        weighted_apr = (
            sum(d["current_balance"] * d["apr"] for d in debts) / total_balance
            if total_balance else 0.0
        )

        strategy = request.args.get("strategy", "avalanche")
        extra_monthly = request.args.get("extra", type=float) or 0.0
        result = debt_engine.simulate_payoff(debts, extra_monthly, strategy)

        edit_id = request.args.get("edit", type=int)
        edit_debt = crud.get_row("debts", edit_id) if edit_id else None

        return render_template(
            "debts.html",
            debts=debts,
            total_balance=total_balance,
            total_min_payment=total_min_payment,
            weighted_apr=weighted_apr,
            strategy=strategy,
            extra_monthly=extra_monthly,
            result=result,
            edit_debt=edit_debt,
        )

    @app.route("/debts", methods=["POST"])
    def debt_create():
        data = {
            "name": request.form.get("name", "").strip(),
            "owner": request.form.get("owner", "").strip() or None,
            "current_balance": request.form.get("current_balance", type=float),
            "apr": request.form.get("apr", type=float),
            "min_payment": request.form.get("min_payment", type=float),
            "due_day": request.form.get("due_day", type=int),
        }
        if not data["name"] or data["current_balance"] is None or data["apr"] is None or data["min_payment"] is None:
            flash("Please fill in name, balance, APR, and minimum payment.")
            return redirect(url_for("debts_page"))
        crud.create_row("debts", data)
        flash(f"Added debt '{data['name']}'.")
        return redirect(url_for("debts_page"))

    @app.route("/debts/<int:row_id>/edit", methods=["POST"])
    def debt_edit(row_id):
        data = {
            "name": request.form.get("name", "").strip(),
            "owner": request.form.get("owner", "").strip() or None,
            "current_balance": request.form.get("current_balance", type=float),
            "apr": request.form.get("apr", type=float),
            "min_payment": request.form.get("min_payment", type=float),
            "due_day": request.form.get("due_day", type=int),
        }
        if not data["name"] or data["current_balance"] is None or data["apr"] is None or data["min_payment"] is None:
            flash("Please fill in name, balance, APR, and minimum payment.")
            return redirect(url_for("debts_page", edit=row_id))
        crud.update_row("debts", row_id, data)
        flash(f"Updated debt '{data['name']}'.")
        return redirect(url_for("debts_page"))

    @app.route("/debts/<int:row_id>/delete", methods=["POST"])
    def debt_delete(row_id):
        crud.delete_row("debts", row_id)
        flash("Debt deleted.")
        return redirect(url_for("debts_page"))

    # ---------- Investments page ----------

    @app.route("/investments", methods=["GET"])
    def investments_page():
        accounts = crud.list_rows("investment_accounts")
        income_sources = crud.list_rows("income_sources")
        income_sources_by_id = {s["id"]: s for s in income_sources}

        horizon_years = request.args.get("years", type=int) or 10
        projection = investment_engine.project_growth(
            accounts, income_sources_by_id, months=horizon_years * 12
        )

        return render_template(
            "investments.html",
            accounts=accounts,
            income_sources=income_sources,
            horizon_years=horizon_years,
            projection=projection,
        )

    @app.route("/investments", methods=["POST"])
    def investment_create():
        data = {
            "owner": request.form.get("owner", "").strip(),
            "name": request.form.get("name", "").strip(),
            "account_type": request.form.get("account_type", "").strip(),
            "current_balance": request.form.get("current_balance", type=float),
            "contribution_percent": request.form.get("contribution_percent", type=float),
            "employer_match_percent": request.form.get("employer_match_percent", type=float),
            "expected_annual_return": request.form.get("expected_annual_return", type=float),
            "linked_income_source_id": request.form.get("linked_income_source_id", type=int) or None,
        }
        if not data["owner"] or not data["name"] or data["current_balance"] is None:
            flash("Please fill in owner, name, and current balance.")
            return redirect(url_for("investments_page"))
        crud.create_row("investment_accounts", data)
        flash(f"Added investment account '{data['name']}'.")
        return redirect(url_for("investments_page"))

    @app.route("/investments/<int:row_id>/delete", methods=["POST"])
    def investment_delete(row_id):
        crud.delete_row("investment_accounts", row_id)
        flash("Investment account deleted.")
        return redirect(url_for("investments_page"))

    @app.route("/investments/<int:row_id>/balance", methods=["POST"])
    def investment_update_balance(row_id):
        new_balance = request.form.get("current_balance", type=float)
        if new_balance is not None:
            crud.update_row("investment_accounts", row_id, {"current_balance": new_balance})
            flash("Balance updated.")
        return redirect(url_for("investments_page"))

    # ---------- Generic REST API: /api/<table> and /api/<table>/<id> ----------

    @app.route("/api/<table>", methods=["GET"])
    def api_list(table):
        try:
            # Optional simple filtering via query string, e.g. ?month=2026-07
            filters = request.args.to_dict()
            rows = crud.list_rows(table, filters or None)
            return jsonify(rows)
        except crud.InvalidTable as e:
            return jsonify({"error": str(e)}), 404

    @app.route("/api/<table>", methods=["POST"])
    def api_create(table):
        try:
            data = request.get_json(force=True, silent=True) or {}
            row = crud.create_row(table, data)
            return jsonify(row), 201
        except crud.InvalidTable as e:
            return jsonify({"error": str(e)}), 404
        except crud.InvalidColumn as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/api/<table>/<int:row_id>", methods=["GET"])
    def api_get_one(table, row_id):
        try:
            row = crud.get_row(table, row_id)
            if row is None:
                return jsonify({"error": "not found"}), 404
            return jsonify(row)
        except crud.InvalidTable as e:
            return jsonify({"error": str(e)}), 404

    @app.route("/api/<table>/<int:row_id>", methods=["PUT"])
    def api_update(table, row_id):
        try:
            data = request.get_json(force=True, silent=True) or {}
            if crud.get_row(table, row_id) is None:
                return jsonify({"error": "not found"}), 404
            row = crud.update_row(table, row_id, data)
            return jsonify(row)
        except crud.InvalidTable as e:
            return jsonify({"error": str(e)}), 404
        except crud.InvalidColumn as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/api/<table>/<int:row_id>", methods=["DELETE"])
    def api_delete(table, row_id):
        try:
            if crud.get_row(table, row_id) is None:
                return jsonify({"error": "not found"}), 404
            crud.delete_row(table, row_id)
            return "", 204
        except crud.InvalidTable as e:
            return jsonify({"error": str(e)}), 404

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    return app


if __name__ == "__main__":
    app = create_app()
    # debug=True auto-reloads on file changes -- great for dev, turn off later
    app.run(host="0.0.0.0", port=5000, debug=True)
