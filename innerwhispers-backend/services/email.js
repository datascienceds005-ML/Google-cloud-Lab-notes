const nodemailer = require('nodemailer');
require('dotenv').config();

const SMTP_PASS = process.env.SMTP_PASS || process.env.BREVO_API_KEY;

const mailTransporter = nodemailer.createTransport({
  host: process.env.SMTP_HOST || 'smtp-relay.brevo.com',
  port: parseInt(process.env.SMTP_PORT || '587'),
  secure: process.env.SMTP_SECURE === 'true',
  auth: {
    user: process.env.SMTP_USER || 'b0cea3001@smtp-brevo.com',
    pass: SMTP_PASS,
  },
  connectionTimeout: 10000,
  greetingTimeout: 10000,
  socketTimeout: 15000,
});

async function sendEmail({ to, subject, html }) {
  const mailOptions = {
    from: `"InnerWhispers Admin" <${process.env.SMTP_USER || 'support@innerwhispers.in'}>`,
    to,
    subject,
    html
  };
  return mailTransporter.sendMail(mailOptions);
}

module.exports = { mailTransporter, sendEmail };
