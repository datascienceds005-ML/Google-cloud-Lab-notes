const express = require('express');
const router = express.Router();
const { db, executeQuery } = require('../config/db');

// --- Transactions Endpoints ---
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
    if (err) return res.status(500).json({ error: 'Database error' });
    res.json(rows);
  });
});

router.get('/summary', (req, res) => {
  const incomeQuery = 'SELECT SUM(amount) AS totalIncome FROM transactions WHERE type="income"';
  const expenseQuery = 'SELECT SUM(amount) AS totalExpenses FROM transactions WHERE type="expense"';

  db.query(incomeQuery, (incomeErr, incomeRows) => {
    if (incomeErr) return res.status(500).json({ error: 'Failed income query' });
    db.query(expenseQuery, (expenseErr, expenseRows) => {
      if (expenseErr) return res.status(500).json({ error: 'Failed expense query' });
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

  db.query(expenseSummaryQuery, (err, expenseRows) => {
    if (err) return res.status(500).json({ error: 'Error fetching expense summary' });
    res.json(expenseRows[0] || {});
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
      if (catErr) return res.status(500).json({ error: 'Failed categories' });
      res.json({ id: budgetId });
    });
  });
});

router.get('/budgets', (req, res) => {
  db.query('SELECT * FROM budgets ORDER BY id DESC', (err, budgets) => {
    if (err) return res.status(500).json({ error: 'Failed' });
    res.json(budgets);
  });
});

// --- Payments, Invoices, Receipts & Settings ---
router.get('/payments', (req, res) => {
  db.query('SELECT * FROM payments ORDER BY received_date DESC, id DESC', (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(rows);
  });
});

router.get('/invoices', (req, res) => {
  db.query('SELECT * FROM invoices ORDER BY due_date DESC, id DESC', (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(rows);
  });
});

router.get('/receipts', (req, res) => {
  db.query('SELECT * FROM receipts ORDER BY issue_date DESC', (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(rows);
  });
});

router.get('/income-trend', (req, res) => {
  const query = `
    SELECT DATE_FORMAT(issue_date, '%Y-%m') AS month, SUM(amount) AS amount
    FROM invoices
    WHERE issue_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
    GROUP BY month ORDER BY month
  `;
  db.query(query, (err, results) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(results);
  });
});

router.get('/settings', (req, res) => {
  db.query('SELECT * FROM settings LIMIT 1', (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(rows[0] || {});
  });
});

module.exports = router;
