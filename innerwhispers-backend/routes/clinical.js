const express = require('express');
const router = express.Router();
const { db } = require('../config/db');

router.get('/patients', (req, res) => {
  const query = "SELECT DISTINCT patient_name FROM appointments WHERE status = 'confirmed' ORDER BY patient_name";
  db.query(query, (err, results) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(results);
  });
});

router.post('/prescriptions', (req, res) => {
  const { patient_name, medication_name, medication_type, medication_dosage, medication_supply, special_instructions, notes } = req.body;
  const query = `
    INSERT INTO prescriptions 
    (patient_name, prescription_date, medication_name, medication_type, medication_dosage, medication_supply, special_instructions, notes)
    VALUES (?, CURDATE(), ?, ?, ?, ?, ?, ?)
  `;
  db.query(query, [patient_name, medication_name, medication_type, medication_dosage, medication_supply, special_instructions, notes], (err, result) => {
    if (err) return res.status(500).json({ error: err.message });
    res.status(201).json({ id: result.insertId, message: 'Prescription created successfully' });
  });
});

router.get('/prescriptions', (req, res) => {
  db.query("SELECT * FROM prescriptions ORDER BY prescription_date DESC, created_at DESC", (err, results) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(results);
  });
});

router.get('/prescriptions/search', (req, res) => {
  const { query: searchQuery } = req.query;
  if (!searchQuery) return res.status(400).json({ error: 'Search query is required' });
  const query = "SELECT * FROM prescriptions WHERE patient_name LIKE ? OR medication_name LIKE ? ORDER BY prescription_date DESC";
  const searchTerm = `%${searchQuery}%`;
  db.query(query, [searchTerm, searchTerm], (err, results) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(results);
  });
});

router.get('/prescriptions/:id', (req, res) => {
  db.query("SELECT * FROM prescriptions WHERE id = ?", [req.params.id], (err, results) => {
    if (err) return res.status(500).json({ error: err.message });
    if (results.length === 0) return res.status(404).json({ error: 'Prescription not found' });
    res.json(results[0]);
  });
});

module.exports = router;

