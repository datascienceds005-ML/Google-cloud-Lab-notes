const mysql = require('mysql2');
require('dotenv').config();

const requiredEnvVars = ['DB_HOST', 'DB_USER', 'DB_NAME'];
const missing = requiredEnvVars.filter(env => !process.env[env]);
if (missing.length > 0) {
  console.error('❌ Missing ENV vars:', missing.join(', '));
  process.exit(1);
}

const dbConfig = {
  host: process.env.DB_HOST,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  port: process.env.DB_PORT || 3306,
  waitForConnections: true,
  connectionLimit: process.env.NODE_ENV === 'production' ? 5 : 10,
  queueLimit: 0,
  dateStrings: true,
  timezone: '+05:30',
};

const db = mysql.createPool(dbConfig);

function executeQuery(sql, params = []) {
  return new Promise((resolve, reject) => {
    db.query(sql, params, (err, results) => {
      if (err) return reject(err);
      resolve([results]);
    });
  });
}

module.exports = { db, executeQuery };
