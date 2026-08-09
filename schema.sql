-- Finance Dashboard schema
-- SQLite. Run once via database.py's init_db().

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS income_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner TEXT NOT NULL,                     -- e.g. 'Caleb' or 'Wife'
    name TEXT NOT NULL,                      -- e.g. 'Primary Job'
    pay_frequency TEXT NOT NULL,             -- 'weekly' | 'biweekly' | 'monthly' | 'semimonthly'
    pay_type TEXT NOT NULL DEFAULT 'salary', -- 'salary' | 'hourly'
    hourly_rate REAL,                        -- only set when pay_type = 'hourly'
    hours_per_week REAL,                     -- only set when pay_type = 'hourly'
    expected_gross_monthly REAL NOT NULL,    -- for salary: entered directly. for hourly: rate * hours/week * 52/12
    effective_tax_rate REAL NOT NULL,        -- e.g. 0.22 for 22%
    start_date TEXT
);

CREATE TABLE IF NOT EXISTS income_actuals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    income_source_id INTEGER NOT NULL,
    month TEXT NOT NULL,                     -- 'YYYY-MM'
    gross_actual REAL,
    net_actual REAL,
    FOREIGN KEY (income_source_id) REFERENCES income_sources(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS expense_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    monthly_budget REAL NOT NULL,            -- the amount entered, at whatever `frequency` below is
    frequency TEXT NOT NULL DEFAULT 'monthly', -- 'weekly' | 'biweekly' | 'monthly' | 'semiannually' | 'annually'
    due_day INTEGER                          -- day of month this bill is due (1-31), optional
);

CREATE TABLE IF NOT EXISTS expense_actuals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    month TEXT NOT NULL,                     -- 'YYYY-MM'
    amount_actual REAL NOT NULL,
    FOREIGN KEY (category_id) REFERENCES expense_categories(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS debts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                      -- e.g. 'Car Loan - Beetle'
    current_balance REAL NOT NULL,
    apr REAL NOT NULL,                       -- e.g. 0.0649 for 6.49%
    min_payment REAL NOT NULL,
    owner TEXT,
    due_day INTEGER                          -- day of month the minimum payment is due (1-31)
);

CREATE TABLE IF NOT EXISTS debt_payment_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    debt_id INTEGER NOT NULL,
    month TEXT NOT NULL,
    payment_amount REAL NOT NULL,
    principal_portion REAL,
    interest_portion REAL,
    balance_after REAL,
    FOREIGN KEY (debt_id) REFERENCES debts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS investment_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner TEXT NOT NULL,
    name TEXT NOT NULL,                      -- e.g. '401k - Fidelity'
    account_type TEXT NOT NULL,              -- '401k' | '403b' | 'brokerage' | 'roth_ira' | etc.
    current_balance REAL NOT NULL,
    contribution_percent REAL,               -- % of linked income, e.g. 0.06
    employer_match_percent REAL,
    expected_annual_return REAL,             -- e.g. 0.07 for 7%
    linked_income_source_id INTEGER,
    FOREIGN KEY (linked_income_source_id) REFERENCES income_sources(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS investment_contribution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    month TEXT NOT NULL,
    contribution_amount REAL NOT NULL,
    balance_after REAL,
    FOREIGN KEY (account_id) REFERENCES investment_accounts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS net_worth_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL UNIQUE,               -- 'YYYY-MM'
    total_savings REAL,
    total_investments REAL,
    total_debt REAL,
    net_worth REAL
);
