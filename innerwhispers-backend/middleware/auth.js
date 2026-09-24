const jwt = require('jsonwebtoken');
const JWT_SECRET = process.env.SECRET_KEY;

function encodeToken(payload) {
  return jwt.sign(payload, JWT_SECRET, { expiresIn: '4h' });
}

function decodeToken(token) {
  try {
    return jwt.verify(token, JWT_SECRET);
  } catch (e) {
    return null;
  }
}

function authenticateToken(req, res, next) {
  const authHeader = req.headers["authorization"];
  const token = authHeader && authHeader.split(" ")[1];

  if (!token) return res.status(401).json({ message: "No token provided" });

  jwt.verify(token, JWT_SECRET, (err, user) => {
    if (err) {
      const message = err.name === 'TokenExpiredError' ? 'Token has expired' : 'Invalid token';
      return res.status(403).json({ message });
    }
    req.user = user;
    next();
  });
}

module.exports = { encodeToken, decodeToken, authenticateToken };
