const express = require('express');
const router = express.Router();
const { executeQuery, db } = require('../config/db');
const { authenticateToken } = require('../middleware/auth');

router.get('/notifications', authenticateToken, async (req, res) => {
  try {
    const role = req.user.role;
    const internId = req.user.intern_id;

    let query = 'SELECT * FROM notifications WHERE 1=1';
    let params = [];

    if (role === 'Intern') {
      query += ' AND (target_role = "Intern" OR target_intern_id = ?) ORDER BY created_at DESC LIMIT 50';
      params.push(internId);
    } else {
      query += ' ORDER BY created_at DESC LIMIT 50';
    }

    const [rows] = await executeQuery(query, params);
    res.json(rows);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.post('/notifications', async (req, res) => {
  try {
    const { title, message, type, target_role, target_intern_id } = req.body;
    const query = `
      INSERT INTO notifications (title, message, type, target_role, target_intern_id, created_at)
      VALUES (?, ?, ?, ?, ?, NOW())
    `;
    const [result] = await executeQuery(query, [title, message, type || 'info', target_role, target_intern_id]);
    res.status(201).json({ message: 'Notification created', id: result.insertId });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.put('/notifications/:id/read', async (req, res) => {
  try {
    const { id } = req.params;
    await executeQuery('UPDATE notifications SET is_read = 1 WHERE id = ?', [id]);
    res.json({ message: 'Marked as read' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.put('/notifications/read-all', authenticateToken, async (req, res) => {
  try {
    const internId = req.user.intern_id;
    if (internId) {
      await executeQuery('UPDATE notifications SET is_read = 1 WHERE target_intern_id = ?', [internId]);
    } else {
      await executeQuery('UPDATE notifications SET is_read = 1 WHERE target_role = "Admin"');
    }
    res.json({ message: 'All notifications marked as read' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.get('/notifications/unread-count', authenticateToken, async (req, res) => {
  try {
    const internId = req.user.intern_id;
    let query = 'SELECT COUNT(*) as unreadCount FROM notifications WHERE is_read = 0';
    let params = [];

    if (internId) {
      query += ' AND (target_intern_id = ? OR target_role = "Intern")';
      params.push(internId);
    }

    const [rows] = await executeQuery(query, params);
    res.json({ unreadCount: rows[0]?.unreadCount || 0 });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
