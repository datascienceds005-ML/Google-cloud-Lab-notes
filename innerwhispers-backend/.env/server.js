const express = require('express');
const helmet = require('helmet');
const compression = require('compression');
const cors = require('cors');
const http = require('http');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3006;

// Middlewares
app.use(helmet());
app.use(compression());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));
app.use(cors({ origin: "*", credentials: true }));

// ✅ Modular Routes Mounting
const financeRoutes = require('./routes/finance.routes');
const doctorRoutes = require('./routes/doctor.routes');
const adminRoutes = require('./routes/admin.routes');

app.use('/api', financeRoutes);  // Transactions, Budgets, Invoices, Payments
app.use('/api', doctorRoutes);   // Appointments, Doctors, Prescriptions
app.use('/api', adminRoutes);    // Admin Stats, Interns, Attendance, Tasks, Leaves

// Health Check
app.get('/health', (req, res) => res.send('✅ Healthy'));

const server = http.createServer(app);
server.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 Modular Server running on port ${PORT}`);
});
