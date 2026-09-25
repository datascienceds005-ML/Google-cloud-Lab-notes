"""
routers/finance.py
Converted 1:1 from server.js lines 4762-5235 (transactions, budgets,
payments, invoices, receipts, irsummary, income-trend, settings).

IMPORTANT — preserved as-is from the source: none of these 12 endpoints
had `authenticateToken` attached in server.js, so none require auth here
either. Flagging this because it's unusual for financial data — worth
confirming with your architect whether that was intentional before you
ship this router. See the SECURITY NOTE further down re: /api/expenseSummary.
"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from typing import Optional

from database import execute_query, execute_write, execute_many

router = APIRouter(tags=["finance"])


# --- Transactions ---

@router.get("/api/transactions")
async def get_transactions(
    type: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
):
    """Mirrors app.get('/api/transactions', ...) — server.js lines 4762-4787."""
    sql = "SELECT * FROM transactions WHERE 1=1"
    params: list = []

    if type and type in ("income", "expense"):
        sql += " AND type = %s"
        params.append(type)

    if search:
        sql += " AND description LIKE %s"
        params.append(f"%{search}%")

    sql += " ORDER BY id DESC"

    try:
        rows = await execute_query(sql, params)
        return rows
    except Exception as err:
        print(f"Failed to fetch transactions: {err}")
        return JSONResponse(status_code=500, content={"error": "Failed to fetch transactions"})


@router.get("/api/filtertransactions")
async def filter_transactions(
    fromDate: Optional[str] = Query(default=None),
    toDate: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
):
    """Mirrors app.get('/api/filtertransactions', ...) — lines 4789-4820."""
    sql = "SELECT * FROM transactions WHERE type='expense'"
    params: list = []

    if fromDate:
        sql += " AND date >= %s"
        params.append(fromDate)

    if toDate:
        sql += " AND date <= %s"
        params.append(toDate)

    if category and category != "All":
        sql += " AND category = %s"
        params.append(category)

    sql += " ORDER BY date DESC"

    try:
        rows = await execute_query(sql, params)
        print(rows)  # console.log(rows) parity with the original
        return rows
    except Exception as err:
        print(f"Error fetching filtered transactions: {err}")
        return JSONResponse(status_code=500, content={"error": "Database error while filtering transactions"})


@router.get("/api/summary")
async def get_summary():
    """Mirrors app.get('/api/summary', ...) — lines 4823-4852.
    Original ran two sequential db.query calls (income, then expense);
    order preserved here for identical behavior, though they could be
    parallelized with asyncio.gather if you want a later optimization."""
    try:
        income_rows = await execute_query(
            'SELECT SUM(amount) AS totalIncome FROM transactions WHERE type="income"'
        )
        expense_rows = await execute_query(
            'SELECT SUM(amount) AS totalExpenses FROM transactions WHERE type="expense"'
        )
    except Exception as err:
        print(f"Failed to fetch income/expense summary: {err}")
        return JSONResponse(status_code=500, content={"error": "Failed to fetch income summary"})

    total_income = income_rows[0]["totalIncome"] or 0
    total_expenses = expense_rows[0]["totalExpenses"] or 0
    net_profit = total_income - total_expenses
    budget_utilization = min(round((total_expenses / 100000) * 100), 100)

    return {
        "totalIncome": total_income,
        "totalExpenses": total_expenses,
        "netProfit": net_profit,
        "budgetUtilization": budget_utilization,
    }


@router.get("/api/expenseSummary")
async def get_expense_summary(category: Optional[str] = Query(default=None)):
    """Mirrors app.get('/api/expenseSummary', ...) — lines 4854-4920.

    SECURITY NOTE: the original built the category filter via raw string
    interpolation —
        JS template literal producing "AND category='<value>'" when category != "All"
    — which is a SQL-injection hole (category comes straight from the
    querystring). This conversion keeps the exact same query logic and
    response shape but parameterizes the value instead of interpolating
    it. This is the one place I deliberately deviated from "identical
    code" to avoid reproducing a known vulnerability — flag if you'd
    rather I match the original byte-for-byte instead.
    """
    category_clause = ""
    params: list = []
    if category and category != "All":
        category_clause = "AND category = %s"
        params.append(category)

    expense_summary_sql = f"""
        SELECT
          SUM(approval_status='Approved') AS approved,
          SUM(CASE WHEN approval_status='Pending' THEN amount ELSE 0 END) AS pending,
          SUM(CASE WHEN approval_status='Rejected' THEN amount ELSE 0 END) AS rejected,
          SUM(amount) AS totalExpenses
        FROM transactions
        WHERE type='expense' {category_clause}
    """
    monthly_sql = f"""
        SELECT DATE_FORMAT(date, '%b') AS month, SUM(amount) AS total
        FROM transactions
        WHERE type='expense' {category_clause}
        GROUP BY MONTH(date)
        ORDER BY MONTH(date)
    """
    category_sql = """
        SELECT category, SUM(amount) AS total
        FROM transactions
        WHERE type='expense'
        GROUP BY category
    """

    try:
        expense_rows = await execute_query(expense_summary_sql, params)
        expense_data = expense_rows[0]
        print(expense_data)

        monthly_rows = await execute_query(monthly_sql, params)
        category_rows = await execute_query(category_sql)
    except Exception as err:
        print(f"Error in expenseSummary: {err}")
        return JSONResponse(status_code=500, content={"error": "Error fetching expense summary"})

    months = [r["month"] for r in monthly_rows]
    monthly_expenses = [r["total"] for r in monthly_rows]
    category_breakdown = {r["category"]: r["total"] for r in category_rows}

    return {
        "totalExpenses": expense_data["totalExpenses"] or 0,
        "approved": expense_data["approved"] or 0,
        "pending": expense_data["pending"] or 0,
        "rejected": expense_data["rejected"] or 0,
        "months": months,
        "monthlyExpenses": monthly_expenses,
        "categoryBreakdown": category_breakdown,
    }


# --- Budgets ---

@router.post("/api/budgets")
async def create_budget(payload: dict):
    """Mirrors app.post('/api/budgets', ...) — lines 4925-4945.
    Kept as a raw dict (rather than a strict Pydantic model) since the
    original did zero validation on req.body; tighten this with a
    BudgetCreate schema once the real field set/required-ness is
    confirmed with the team."""
    print("body", payload)
    name = payload.get("name")
    allocated = payload.get("allocated")
    duration = payload.get("duration")
    categories = payload.get("categories") or []

    try:
        result = await execute_write(
            "INSERT INTO budgets (name, total_amount, duration) VALUES (%s, %s, %s)",
            (name, allocated, duration),
        )
        budget_id = result["insert_id"]

        cat_values = [(budget_id, cat["name"], cat["amount"]) for cat in categories]
        if cat_values:
            await execute_many(
                "INSERT INTO budget_categories (budget_id, name, amount) VALUES (%s, %s, %s)",
                cat_values,
            )

        return {"id": budget_id}
    except Exception as err:
        print(f"Failed to create budget: {err}")
        return JSONResponse(status_code=500, content={"error": "Failed to create budget"})


@router.get("/api/budgets")
async def list_budgets():
    """Mirrors app.get('/api/budgets', ...) — lines 4948-4982.
    Original fired N+1 queries (one per budget for its categories) using
    a manual pending-counter to know when to respond. We keep the same
    N+1 query pattern for behavioral parity, just sequentially awaited
    instead of callback-counted."""
    try:
        budgets = await execute_query("SELECT * FROM budgets ORDER BY id DESC")
    except Exception as err:
        print(f"Failed to fetch budgets: {err}")
        return JSONResponse(status_code=500, content={"error": "Failed to fetch budgets"})

    if not budgets:
        return []

    for budget in budgets:
        try:
            categories = await execute_query(
                "SELECT name, amount FROM budget_categories WHERE budget_id = %s",
                (budget["id"],),
            )
            budget["categories"] = categories
        except Exception as cat_err:
            print(f"Failed to fetch budget categories: {cat_err}")
            budget["categories"] = []

    return budgets


# --- Payments ---

@router.get("/api/payments")
async def get_payments(
    search: str = Query(default=""),
    status: Optional[str] = Query(default=None),
):
    """Mirrors app.get('/api/payments', ...) — lines 4986-5011."""
    sql = "SELECT * FROM payments WHERE 1=1"
    params: list = []

    if status and status in ("Succeeded", "Pending", "Failed"):
        sql += " AND status = %s"
        params.append(status)

    if search:
        sql += " AND (payment_id LIKE %s OR client_name LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])

    sql += " ORDER BY received_date DESC, id DESC"

    try:
        return await execute_query(sql, params)
    except Exception as err:
        print(f"Failed to fetch payments: {err}")
        return JSONResponse(status_code=500, content={"error": "Failed to fetch payments"})


# --- Invoices ---

@router.get("/api/invoices")
async def get_invoices(
    search: str = Query(default=""),
    status: Optional[str] = Query(default=None),
):
    """Mirrors app.get('/api/invoices', ...) — lines 5015-5040."""
    sql = "SELECT * FROM invoices WHERE 1=1"
    params: list = []

    if status and status in ("Paid", "Pending", "Overdue"):
        sql += " AND status = %s"
        params.append(status)

    if search:
        sql += " AND (invoice_number LIKE %s OR client_name LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])

    sql += " ORDER BY due_date DESC, id DESC"

    try:
        return await execute_query(sql, params)
    except Exception as err:
        print(f"Failed to fetch invoices: {err}")
        return JSONResponse(status_code=500, content={"error": "Failed to fetch invoices"})


@router.get("/api/receipts")
async def get_receipts(search: str = Query(default="")):
    """Mirrors app.get('/api/receipts', ...) — lines 5042-5062."""
    sql = "SELECT * FROM receipts WHERE 1=1"
    params: list = []

    if search:
        sql += " AND (receipt_number LIKE %s OR client_name LIKE %s OR invoice_number LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    sql += " ORDER BY issue_date DESC"

    try:
        return await execute_query(sql, params)
    except Exception as err:
        print(f"Failed to fetch receipts: {err}")
        return JSONResponse(status_code=500, content={"error": "Failed to fetch receipts"})


@router.get("/api/irsummary")
async def get_ir_summary(search: str = Query(default="")):
    """Mirrors app.get('/api/irsummary', ...) — lines 5064-5142.
    Original nested three sequential db.query calls (totals → receipts →
    invoices) to build one combined response; order preserved."""
    totals_sql = """
        SELECT
          (SELECT IFNULL(SUM(amount), 0) FROM invoices) AS totalInvoiced,
          (SELECT IFNULL(SUM(amount), 0) FROM receipts) AS receiptsIssued,
          (SELECT IFNULL(SUM(amount), 0) FROM invoices) - (SELECT IFNULL(SUM(amount), 0) FROM receipts) AS outstanding
    """
    try:
        totals_rows = await execute_query(totals_sql)
    except Exception as err:
        print(f"Failed to fetch totals: {err}")
        return JSONResponse(status_code=500, content={"error": "Failed to fetch totals"})

    receipts_sql = """
        SELECT
          receipt_number,
          client_name,
          invoice_number,
          amount,
          DATE_FORMAT(created_at, "%Y-%m-%d") AS issueDate
        FROM receipts
        WHERE 1=1
    """
    receipts_params: list = []
    if search:
        receipts_sql += " AND (receipt_number LIKE %s OR client_name LIKE %s OR invoice_number LIKE %s)"
        receipts_params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    receipts_sql += " ORDER BY issueDate DESC LIMIT 100"

    try:
        receipts_rows = await execute_query(receipts_sql, receipts_params)
    except Exception as err:
        print(f"Failed to fetch receipts: {err}")
        return JSONResponse(status_code=500, content={"error": "Failed to fetch receipts"})

    invoices_sql = """
        SELECT
          invoice_number,
          client_name,
          amount,
          DATE_FORMAT(created_at, '%Y-%m-%d') AS issueDate,
          DATE_FORMAT(due_date, '%Y-%m-%d') AS dueDate
        FROM invoices
        WHERE 1=1
    """
    invoices_params: list = []
    if search:
        invoices_sql += " AND (invoice_number LIKE %s OR client_name LIKE %s)"
        invoices_params.extend([f"%{search}%", f"%{search}%"])
    invoices_sql += " ORDER BY issueDate DESC LIMIT 100"

    try:
        invoices_rows = await execute_query(invoices_sql, invoices_params)
    except Exception as err:
        print(f"Failed to fetch invoices: {err}")
        return JSONResponse(status_code=500, content={"error": "Failed to fetch invoices"})

    return {
        "totals": totals_rows[0],
        "receipts": receipts_rows,
        "invoices": invoices_rows,
    }


@router.get("/api/income-trend")
async def get_income_trend():
    """Mirrors app.get('/api/income-trend', ...) — lines 5144-5156."""
    sql = """
        SELECT DATE_FORMAT(issue_date, '%Y-%m') AS month, SUM(amount) AS amount
        FROM invoices
        WHERE issue_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
        GROUP BY month
        ORDER BY month
    """
    try:
        return await execute_query(sql)
    except Exception:
        return JSONResponse(status_code=500, content={"error": "Failed to fetch income trend"})


# --- Settings ---

@router.get("/api/settings")
async def get_settings():
    """Mirrors app.get('/api/settings', ...) — lines 5159-5173."""
    try:
        rows = await execute_query("SELECT * FROM settings LIMIT 1")
    except Exception as err:
        print(f"Failed to fetch settings: {err}")
        return JSONResponse(status_code=500, content={"error": "Failed to fetch settings"})

    if not rows:
        return {}
    return rows[0]


@router.put("/api/settings")
async def update_settings(payload: dict):
    """Mirrors app.put('/api/settings', ...) — lines 5176-5235.
    Same check-then-insert-or-update pattern as the original (not a true
    UPSERT/ON DUPLICATE KEY — kept identical since only one settings row
    is ever expected)."""
    company_name = payload.get("company_name")
    support_email = payload.get("support_email")
    timezone = payload.get("timezone")
    currency = payload.get("currency")
    pay_terms = payload.get("pay_terms")
    tax_rate = payload.get("tax_rate")
    invoice_prefix = payload.get("invoice_prefix")
    auto_send = payload.get("auto_send")

    try:
        rows = await execute_query("SELECT * FROM settings LIMIT 1")
    except Exception as err:
        print(f"Error checking settings: {err}")
        return JSONResponse(status_code=500, content={"error": "Failed to update settings"})

    params = (
        company_name, support_email, timezone, currency,
        pay_terms, tax_rate, invoice_prefix, auto_send,
    )

    if not rows:
        try:
            await execute_write(
                """
                INSERT INTO settings
                (company_name, support_email, timezone, currency, pay_terms, tax_rate, invoice_prefix, auto_send)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                params,
            )
            return {"message": "Settings saved successfully"}
        except Exception as err2:
            print(f"Failed to insert settings: {err2}")
            return JSONResponse(status_code=500, content={"error": "Failed to insert settings"})
    else:
        try:
            await execute_write(
                """
                UPDATE settings SET
                company_name = %s,
                support_email = %s,
                timezone = %s,
                currency = %s,
                pay_terms = %s,
                tax_rate = %s,
                invoice_prefix = %s,
                auto_send = %s
                WHERE id = %s
                """,
                params + (rows[0]["id"],),
            )
            return {"message": "Settings updated successfully"}
        except Exception as err3:
            print(f"Failed to update settings: {err3}")
            return JSONResponse(status_code=500, content={"error": "Failed to update settings"})
