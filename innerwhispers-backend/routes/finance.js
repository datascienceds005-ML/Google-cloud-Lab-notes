const express = require('express');
const router = express.Router();
const { db } = require('../config/db');

// --- Transactions ---
router.get('/transactions', (req, res) => {
  const { type, search } = req.query;
  let sql = 'SELECT * FROM transactions WHERE 1=1';
  const params = [];

  if (type && ['income', 'expense'].includes(type)) {
    sql += ' AND type = ?';
    params.push(type);
  }
  if (search) {
    sql += ' AND description LIKE ?';
    params.push(`%${search}%`);
  }
  sql += ' ORDER BY id DESC';

  db.query(sql, params, (err, rows) => {
    if (err) return res.status(500).json({ error: 'Failed to fetch transactions' });
    res.json(rows);
  });
});

router.get('/filtertransactions', (req, res) => {
  const { fromDate, toDate, category } = req.query;
  let query = `SELECT * FROM transactions WHERE type='expense'`;
  const params = [];

  if (fromDate) { query += ` AND date >= ?`; params.push(fromDate); }
  if (toDate) { query += ` AND date <= ?`; params.push(toDate); }
  if (category && category !== 'All') { query += ` AND category = ?`; params.push(category); }
  query += ` ORDER BY date DESC`;

  db.query(query, params, (err, rows) => {
    if (err) return res.status(500).json({ error: 'Database error while filtering transactions' });
    res.json(rows);
  });
});

router.get('/summary', (req, res) => {
  const incomeQuery = 'SELECT SUM(amount) AS totalIncome FROM transactions WHERE type="income"';
  const expenseQuery = 'SELECT SUM(amount) AS totalExpenses FROM transactions WHERE type="expense"';

  db.query(incomeQuery, (incomeErr, incomeRows) => {
    if (incomeErr) return res.status(500).json({ error: 'Failed to fetch income summary' });
    db.query(expenseQuery, (expenseErr, expenseRows) => {
      if (expenseErr) return res.status(500).json({ error: 'Failed to fetch expense summary' });
      const totalIncome = incomeRows[0]?.totalIncome || 0;
      const totalExpenses = expenseRows[0]?.totalExpenses || 0;
      res.json({
        totalIncome,
        totalExpenses,
        netProfit: totalIncome - totalExpenses,
        budgetUtilization: Math.min(Math.round((totalExpenses / 100000) * 100), 100)
      });
    });
  });
});

router.get('/expenseSummary', (req, res) => {
  const { category } = req.query;
  const categoryFilter = category && category !== 'All' ? `AND category='${category}'` : '';

  const expenseSummaryQuery = `
    SELECT 
      SUM(approval_status='Approved') AS approved,
      SUM(CASE WHEN approval_status='Pending' THEN amount ELSE 0 END) AS pending,
      SUM(CASE WHEN approval_status='Rejected' THEN amount ELSE 0 END) AS rejected,
      SUM(amount) AS totalExpenses
    FROM transactions
    WHERE type='expense' ${categoryFilter}
  `;

  const monthlyQuery = `
    SELECT DATE_FORMAT(date, '%b') AS month, SUM(amount) AS total
    FROM transactions
    WHERE type='expense' ${categoryFilter}
    GROUP BY MONTH(date) ORDER BY MONTH(date)
  `;

  const categoryQuery = `
    SELECT category, SUM(amount) AS total
    FROM transactions WHERE type='expense' GROUP BY category
  `;

  db.query(expenseSummaryQuery, (err, expenseRows) => {
    if (err) return res.status(500).json({ error: 'Error fetching expense summary' });
    const expenseData = expenseRows[0];

    db.query(monthlyQuery, (err2, monthlyRows) => {
      if (err2) return res.status(500).json({ error: 'Error fetching monthly expenses' });
      db.query(categoryQuery, (err3, categoryRows) => {
        if (err3) return res.status(500).json({ error: 'Error fetching category breakdown' });
        const months = monthlyRows.map(r => r.month);
        const monthlyExpenses = monthlyRows.map(r => r.total);
        const categoryBreakdown = {};
        categoryRows.forEach(r => (categoryBreakdown[r.category] = r.total));

        res.json({
          totalExpenses: expenseData?.totalExpenses || 0,
          approved: expenseData?.approved || 0,
          pending: expenseData?.pending || 0,
          rejected: expenseData?.rejected || 0,
          months,
          monthlyExpenses,
          categoryBreakdown
        });
      });
    });
  });
});

// --- Budgets ---
router.post('/budgets', (req, res) => {
  const { name, allocated, duration, categories } = req.body;
  const sql = 'INSERT INTO budgets (name, total_amount, duration) VALUES (?, ?, ?)';
  db.query(sql, [name, allocated, duration], (err, result) => {
    if (err) return res.status(500).json({ error: 'Failed to create budget' });
    const budgetId = result.insertId;
    if (!categories || categories.length === 0) return res.json({ id: budgetId });
    const catSql = 'INSERT INTO budget_categories (budget_id, name, amount) VALUES ?';
    const catValues = categories.map(cat => [budgetId, cat.name, cat.amount]);
    db.query(catSql, [catValues], (catErr) => {
      if (catErr) return res.status(500).json({ error: 'Failed to create budget categories' });
      res.json({ id: budgetId });
    });
  });
});

router.get('/budgets', (req, res) => {
  const sql = 'SELECT * FROM budgets ORDER BY id DESC';
  db.query(sql, (err, budgets) => {
    if (err) return res.status(500).json({ error: 'Failed to fetch budgets' });
    if (budgets.length === 0) return res.json([]);
    let pending = budgets.length;
    budgets.forEach((budget, index) => {
      const catSql = 'SELECT name, amount FROM budget_categories WHERE budget_id = ?';
      db.query(catSql, [budget.id], (catErr, categories) => {
        budgets[index].categories = catErr ? [] : categories;
        pending--;
        if (pending === 0) res.json(budgets);
      });
    });
  });
});

// --- Payments, Invoices, Receipts & Settings ---
router.get('/payments', (req, res) => {
  const { search = '', status } = req.query;
  let sql = 'SELECT * FROM payments WHERE 1=1';
  const params = [];
  if (status && ['Succeeded', 'Pending', 'Failed'].includes(status)) {
    sql += ' AND status = ?'; params.push(status);
  }
  if (search) {
    sql += ' AND (payment_id LIKE ? OR client_name LIKE ?)'; params.push(`%\({search}%`, `%\){search}%`);
  }
  sql += ' ORDER BY received_date DESC, id DESC';
  db.query(sql, params, (err, rows) => {
    if (err) return res.status(500).json({ error: 'Failed to fetch payments' });
    res.json(rows);
  });
});

router.get('/invoices', (req, res) => {
  const { search = '', status } = req.query;
  let sql = 'SELECT * FROM invoices WHERE 1=1';
  const params = [];
  if (status && ['Paid', 'Pending', 'Overdue'].includes(status)) {
    sql += ' AND status = ?'; params.push(status);
  }
  if (search) {
    sql += ' AND (invoice_number LIKE ? OR client_name LIKE ?)'; params.push(`%\({search}%`, `%\){search}%`);
  }
  sql += ' ORDER BY due_date DESC, id DESC';
  db.query(sql, params, (err, rows) => {
    if (err) return res.status(500).json({ error: 'Failed to fetch invoices' });
    res.json(rows);
  });
});

router.get('/receipts', (req, res) => {
  const { search = '' } = req.query;
  let sql = 'SELECT * FROM receipts WHERE 1=1';
  const params = [];
  if (search) {
    sql += ' AND (receipt_number LIKE ? OR client_name LIKE ? OR invoice_number LIKE ?)';
    params.push(`%\({search}%`, `%\){search}%`, `%${search}%`);
  }
  sql += ' ORDER BY issue_date DESC';
  db.query(sql, params, (err, rows) => {
    if (err) return res.status(500).json({ error: 'Failed to fetch receipts' });
    res.json(rows);
  });
});

router.get('/income-trend', (req, res) => {
  const query = `
    SELECT DATE_FORMAT(issue_date, '%Y-%m') AS month, SUM(amount) AS amount
    FROM invoices WHERE issue_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
    GROUP BY month ORDER BY month
  `;
  db.query(query, (err, results) => {
    if (err) return res.status(500).json({ error: 'Failed to fetch income trend' });
    res.json(results);
  });
});

router.get('/settings', (req, res) => {
  db.query('SELECT * FROM settings LIMIT 1', (err, rows) => {
    if (err) return res.status(500).json({ error: 'Failed to fetch settings' });
    res.json(rows[0] || {});
  });
});

router.put('/api/settings', (req, res) => {
  const { company_name, support_email, timezone, currency, pay_terms, tax_rate, invoice_prefix, auto_send } = req.body;
  db.query('SELECT * FROM settings LIMIT 1', (err, rows) => {
    if (err) return res.status(500).json({ error: 'Failed to update settings' });
    if (rows.length === 0) {
      const insertSql = `INSERT INTO settings (company_name, support_email, timezone, currency, pay_terms, tax_rate, invoice_prefix, auto_send) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`;
      db.query(insertSql, [company_name, support_email, timezone, currency, pay_terms, tax_rate, invoice_prefix, auto_send], (err2) => {
        if (err2) return res.status(500).json({ error: 'Failed to insert settings' });
        res.json({ message: 'Settings saved successfully' });
      });
    } else {
      const updateSql = `UPDATE settings SET company_name=?, support_email=?, timezone=?, currency=?, pay_terms=?, tax_rate=?, invoice_prefix=?, auto_send=? WHERE id=?`;
      db.query(updateSql, [company_name, support_email, timezone, currency, pay_terms, tax_rate, invoice_prefix, auto_send, rows[0].id], (err3) => {
        if (err3) return res.status(500).json({ error: 'Failed to update settings' });
        res.json({ message: 'Settings updated successfully' });
      });
    }
  });
});

module.exports = router;
