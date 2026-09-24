const express = require('express');
const router = express.Router();
const { db, executeQuery } = require('../config/db');

// Helper: 24-hour time conversion from server.js
function convertTo24Hour(timeStr) {
  if (!timeStr || typeof timeStr !== 'string') return timeStr;
  try {
    if (timeStr.match(/^([01]?[0-9]|2[0-3]):[0-5][0-9]$/)) return timeStr + ':00';
    const [time, meridiem] = timeStr.split(' ');
    const [hours, minutes] = time.split(':');
    let hour = parseInt(hours);
    if (meridiem.toLowerCase() === 'pm' && hour !== 12) hour += 12;
    else if (meridiem.toLowerCase() === 'am' && hour === 12) hour = 0;
    return `\({hour.toString().padStart(2, '0')}:\){minutes}:00`;
  } catch (error) {
    return null;
  }
}

const SESSION_TYPES = {
  'Initial Consultation': { duration: 40, price: 1000 },
  'Counseling Session': { duration: 50, price: 1500 },
  'Therapy Session': { duration: 80, price: 3000 }
};

// 1. Doctor Profile & UI
router.get('/getalldoc', (req, res) => {
  db.query("SELECT id,full_name FROM doctor_details", (err, results) => {
    if (err) return res.status(500).json({ message: "DB error" });
    res.json(results);
  });
});

router.get('/getdoc/:id', (req, res) => {
  db.query("SELECT id,full_name FROM doctor_details where id=?", [req.params.id], (err, results) => {
    if (err) return res.status(500).json({ message: "DB error" });
    if (results.length === 0) return res.status(404).json({ message: "User not found" });
    res.json(results[0]);
  });
});

router.get('/dashboard_ui/:id', (req, res) => {
  db.query("SELECT * FROM doctor_ui where doctor_id=?", [req.params.id], (err, results) => {
    if (err) return res.status(500).json({ message: "DB error" });
    if (results.length === 0) return res.status(404).json({ message: "User not found" });
    res.json(results[0]);
  });
});

router.put('/dashboard_ui/:id', (req, res) => {
  const doctorId = req.params.id;
  const fields = req.body;
  if (Object.keys(fields).length === 0) return res.status(400).json({ message: "No fields provided" });
  db.query("UPDATE doctor_ui SET ? WHERE doctor_id = ?", [fields, doctorId], (err, results) => {
    if (err) return res.status(500).json({ message: "DB error" });
    res.json({ message: "Update successful" });
  });
});

// 2. Appointments
router.post('/appointments', (req, res) => {
  const time24 = convertTo24Hour(req.body.appointment_time);
  if (!time24) return res.status(400).json({ error: 'Invalid time format' });

  const sessionInfo = SESSION_TYPES[req.body.session_type] || { duration: 50, price: 1500 };
  const query = `
    INSERT INTO appointments 
    SET patient_name=?, email=?, phone=?, addhar=?, age=?, parenttype=?, parentName=?, guardianPhone=?, 
        address=?, pincode=?, state=?, concerns=?, appointment_date=CONVERT_TZ(?, '+00:00', '+05:30'), 
        appointment_time=?, session_type=?, session_price=?, session_duration=?, status=?, created_at=CONVERT_TZ(NOW(), '+00:00', '+05:30')
  `;
  const values = [
    req.body.patient_name, req.body.email, req.body.phone, req.body.addhar, req.body.age,
    req.body.parenttype, req.body.parentName, req.body.guardianPhone, req.body.address,
    req.body.pincode, req.body.state, req.body.concerns, req.body.appointment_date,
    time24, req.body.session_type, sessionInfo.price, sessionInfo.duration, req.body.status || 'pending'
  ];

  db.query(query, values, (err, result) => {
    if (err) return res.status(500).json({ error: err.message });
    res.status(201).json({ message: 'Appointment created successfully', id: result.insertId });
  });
});

router.get('/appointments/:id', (req, res) => {
  const { id } = req.params;
  const query = `
    SELECT *, DATE_FORMAT(CONVERT_TZ(appointment_date, '+00:00', '+05:30'), '%Y-%m-%d') as appointment_date
    FROM appointments WHERE doctor_id=? ORDER BY appointment_date, appointment_time
  `;
  db.query(query, [id], (err, results) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(results);
  });
});

router.put('/appointments/:doc_id/:id/status', (req, res) => {
  const { doc_id, id } = req.params;
  const { status } = req.body;
  db.query('UPDATE appointments SET status = ? WHERE doctor_id = ? AND id = ?', [status, doc_id, id], (err) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ message: 'Status updated successfully' });
  });
});

// 3. Patients & Prescriptions
router.get('/patients', (req, res) => {
  db.query("SELECT DISTINCT patient_name FROM appointments WHERE status = 'confirmed' ORDER BY patient_name", (err, results) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(results);
  });
});

router.post('/prescriptions', (req, res) => {
  const { patient_name, medication_name, medication_type, medication_dosage, medication_supply, special_instructions, notes } = req.body;
  const query = `
    INSERT INTO prescriptions (patient_name, prescription_date, medication_name, medication_type, medication_dosage, medication_supply, special_instructions, notes)
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

router.get('/prescriptions/:id', (req, res) => {
  db.query("SELECT * FROM prescriptions WHERE id = ?", [req.params.id], (err, results) => {
    if (err) return res.status(500).json({ error: err.message });
    if (results.length === 0) return res.status(404).json({ error: 'Prescription not found' });
    res.json(results[0]);
  });
});

module.exports = router;
