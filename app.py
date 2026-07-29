from flask import Flask, jsonify, request, render_template, redirect, url_for, flash

import database
import generic_crud as crud
import helpers


def create_app():
    app = Flask(__name__)
    app.config["DATABASE_PATH"] = "instance/finance.db"
    # Only used to sign the flash-message cookie -- fine as-is for a LAN-only,
    # two-person household tool. Change it if you ever expose this beyond your network.
    app.config["SECRET_KEY"] = "dev-change-me"

    database.register_app(app)

    with app.app_context():
        database.init_db(app)

    # ---------- Dashboard (placeholder for now, built out in a later step) ----------

    @app.route("/")
    def index():
        return render_template("base.html", tables=sorted(crud.ALLOWED_TABLES))

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
        data = {
            "owner": request.form.get("owner", "").strip(),
            "name": request.form.get("name", "").strip(),
            "pay_frequency": request.form.get("pay_frequency", "").strip(),
            "expected_gross_monthly": request.form.get("expected_gross_monthly", type=float),
            "effective_tax_rate": request.form.get("effective_tax_rate", type=float),
            "start_date": request.form.get("start_date") or None,
        }
        if not data["owner"] or not data["name"] or data["expected_gross_monthly"] is None or data["effective_tax_rate"] is None:
            flash("Please fill in owner, name, expected gross monthly, and tax rate.")
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

        budget_total = sum(c["monthly_budget"] for c in categories)
        actual_total = sum(a["amount_actual"] for a in actuals)

        return render_template(
            "expenses.html",
            categories=categories,
            actuals=actuals,
            actual_by_category=actual_by_category,
            month=month,
            budget_total=budget_total,
            actual_total=actual_total,
        )

    @app.route("/expenses/categories", methods=["POST"])
    def expense_category_create():
        data = {
            "name": request.form.get("name", "").strip(),
            "monthly_budget": request.form.get("monthly_budget", type=float),
        }
        if not data["name"] or data["monthly_budget"] is None:
            flash("Please provide a category name and monthly budget.")
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
