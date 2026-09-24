const express = require('express');
const router = express.Router();
const { executeQuery, db } = require('../config/db');
const { authenticateToken } = require('../middleware/auth');
const upload = require('../middleware/upload');

// 1. Intern Directory & Profile
router.get('/interns', authenticateToken, async (req, res) => {
  try {
    const [interns] = await executeQuery('SELECT * FROM Interns ORDER BY created_at DESC');
    res.json({ interns });
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch interns data' });
  }
});

router.get('/getintern/:id', async (req, res) => {
  try {
    const [intern] = await executeQuery('SELECT * FROM Interns WHERE intern_id = ?', [req.params.id]);
    if (intern.length === 0) return res.status(404).json({ message: 'Intern not found' });
    res.json(intern[0]);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// 2. Attendance Records & Checkin
router.get('/attendance/records', authenticateToken, async (req, res) => {
  try {
    const date = req.query.date || new Date().toISOString().slice(0, 10);
    const [rows] = await executeQuery(`
      SELECT a.*, i.name, i.department FROM Attendance a
      LEFT JOIN Interns i ON a.intern_id = i.intern_id WHERE a.attendance_date = ?
    `, [date]);
    res.json(rows);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.post('/attendance/checkinout', async (req, res) => {
  const { intern_id, type } = req.body;
  const today = new Date().toISOString().slice(0, 10);
  try {
    if (type === 'checkin') {
      await executeQuery(`
        INSERT INTO Attendance (intern_id, attendance_date, check_in, status)
        VALUES (?, ?, NOW(), 'Present')
        ON DUPLICATE KEY UPDATE check_in = NOW(), status = 'Present'
      `, [intern_id, today]);
      res.json({ message: 'Check-in successful' });
    } else {
      await executeQuery(`
        UPDATE Attendance SET check_out = NOW() WHERE intern_id = ? AND attendance_date = ?
      `, [intern_id, today]);
      res.json({ message: 'Check-out successful' });
    }
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// 3. Tasks Management
router.get('/tasks/all', async (req, res) => {
  try {
    const internId = req.query.intern_id;
    let sql = 'SELECT * FROM Tasks';
    let params = [];
    if (internId) {
      sql += ' WHERE intern_id = ?';
      params.push(internId);
    }
    const [rows] = await executeQuery(sql, params);
    res.json(rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

router.post('/addtask', (req, res) => {
  const { intern_id, task_title, task_description, priority, status, assigned_date, due_date } = req.body;
  const sql = `INSERT INTO Tasks (intern_id, task_title, task_description, priority, status, assigned_date, due_date) VALUES (?, ?, ?, ?, ?, ?, ?)`;
  db.query(sql, [intern_id, task_title, task_description, priority, status, assigned_date, due_date], (err, result) => {
    if (err) return res.status(500).json({ message: err.message });
    res.json({ message: "Task added successfully", result });
  });
});

router.put('/changetask/:taskId', (req, res) => {
  const { taskId } = req.params;
  const fields = req.body;
  db.query('UPDATE Tasks SET ? WHERE id = ?', [fields, taskId], (err) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ message: 'Task updated successfully' });
  });
});

// 4. Leave Requests
router.post('/leave-requests', async (req, res) => {
  const { intern_id, start_date, end_date, reason, type } = req.body;
  try {
    await executeQuery(`
      INSERT INTO leave_requests (intern_id, start_date, end_date, reason, type, status, requested_at)
      VALUES (?, ?, ?, ?, ?, 'Pending', NOW())
    `, [intern_id, start_date, end_date, reason, type]);
    res.status(201).json({ message: 'Leave request submitted' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.get('/leave-requests/:intern_id?', async (req, res) => {
  try {
    const internId = req.params.intern_id;
    let sql = 'SELECT * FROM leave_requests';
    let params = [];
    if (internId) {
      sql += ' WHERE intern_id = ?';
      params.push(internId);
    }
    sql += ' ORDER BY requested_at DESC';
    const [rows] = await executeQuery(sql, params);
    res.json(rows);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.put('/leave-requests/:id/status', async (req, res) => {
  const { id } = req.params;
  const { status, remarks } = req.body;
  db.query('UPDATE leave_requests SET status = ?, remarks = ? WHERE id = ?', [status, remarks, id], (err) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ message: `Leave request ${status.toLowerCase()} successfully` });
  });
});

// 5. Reports & Documents
router.get('/reports', async (req, res) => {
  try {
    const [rows] = await executeQuery('SELECT * FROM reports ORDER BY uploaded_at DESC');
    res.json(rows);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.get('/documents/all', (req, res) => {
  db.query('SELECT * FROM documents ORDER BY uploaded_at DESC', (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(rows);
  });
});

module.exports = router;
