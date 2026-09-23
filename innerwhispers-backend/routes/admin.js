const express = require('express');
const router = express.Router();
const { executeQuery, db } = require('../config/db');

// Helper to get IST date
function getTodayIST() {
  const now = new Date();
  const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
  const ist = new Date(utc + (5.5 * 60 * 60000));
  return ist.toISOString().slice(0, 10);
}

// 1. Dashboard Overview Stats
router.get('/dashboard/stats', async (req, res) => {
  try {
    const today = getTodayIST();
    const [totalInterns] = await executeQuery('SELECT COUNT(*) as count FROM Interns WHERE status = "Active"');
    const [pendingLeave] = await executeQuery('SELECT COUNT(*) as count FROM leave_requests WHERE status = "Pending"');
    const [todayAttendance] = await executeQuery(
      'SELECT status, COUNT(*) as count FROM Attendance WHERE attendance_date = ? GROUP BY status',
      [today]
    );

    res.json({
      totalInterns: totalInterns[0]?.count || 0,
      pendingLeave: pendingLeave[0]?.count || 0,
      todayAttendance
    });
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch dashboard stats' });
  }
});

// 2. Interns List
router.get('/interns', async (req, res) => {
  try {
    const [interns] = await executeQuery('SELECT * FROM Interns ORDER BY created_at DESC');
    res.json({ interns });
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch interns' });
  }
});

// 3. Attendance Records
router.get('/attendance/records', async (req, res) => {
  try {
    const today = req.query.date || getTodayIST();
    const [rows] = await executeQuery(`
      SELECT a.*, i.name, i.department
      FROM Attendance a
      LEFT JOIN Interns i ON a.intern_id = i.intern_id
      WHERE a.attendance_date = ?
    `, [today]);
    res.json(rows);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// 4. Leave Requests Management
router.get('/dashboard/leave-requests', async (req, res) => {
  try {
    const [rows] = await executeQuery(`
      SELECT lr.*, i.name, i.department
      FROM leave_requests lr
      JOIN Interns i ON lr.intern_id = i.intern_id
      ORDER BY lr.requested_at DESC LIMIT 20
    `);
    res.json(rows);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// 5. Tasks Management
router.get('/tasks/all', async (req, res) => {
  try {
    const [rows] = await executeQuery('SELECT * FROM Tasks WHERE intern_id = ?', [req.query.intern_id]);
    res.json(rows);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
