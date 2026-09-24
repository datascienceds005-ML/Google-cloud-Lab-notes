const multer = require('multer');

// Memory storage for file buffering before Cloudinary/DB processing
const storage = multer.memoryStorage();

const upload = multer({
  storage: storage,
  limits: {
    fileSize: 10 * 1024 * 1024 // 10MB limit
  }
});

module.exports = upload;
