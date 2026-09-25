"""
config.py
Centralized environment configuration.
Mirrors every process.env.* usage found in the original server.js.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    """Fail fast on startup if a required var is missing — mirrors the
    requiredEnvVars check that called process.exit(1) in server.js."""
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


# --- Database (mirrors the `dbConfig` object passed to mysql.createPool) ---
DB_HOST = _required("DB_HOST")
DB_USER = _required("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = _required("DB_NAME")
DB_PORT = int(os.getenv("DB_PORT", "3306"))

# server.js used a smaller pool in production (5) vs dev (10)
NODE_ENV = os.getenv("NODE_ENV", "development")
DB_POOL_MIN_SIZE = 1
DB_POOL_MAX_SIZE = 5 if NODE_ENV == "production" else 10

# server.js pinned the connection timezone to IST (+05:30) and used
# dateStrings: true so MySQL DATE/DATETIME columns came back as plain
# strings rather than JS Date objects. We replicate the timezone pin;
# PyMySQL/aiomysql return native types, which we format explicitly
# wherever server.js relied on dateStrings.
DB_TIMEZONE = "+05:30"

# --- Auth ---
JWT_SECRET = _required("SECRET_KEY")
JWT_ALGORITHM = "HS256"  # jsonwebtoken's default, used implicitly in server.js

# --- Server ---
PORT = int(os.getenv("PORT", "3006"))

# --- Mail (Brevo HTTPS API + SMTP fallback) ---
DEFAULT_HR_EMAIL = os.getenv("HR_EMAIL", "hr.interns.innerwhispers@gmail.com")
DEFAULT_SMTP_FROM = os.getenv(
    "SMTP_FROM", '"InnerWhispers Wellness LLP" <no-reply@innerwhispers.in>'
)
BREVO_API_KEY = os.getenv("BREVO_API_KEY") or os.getenv("SMTP_PASS")
SMTP_PASS = os.getenv("SMTP_PASS") or os.getenv("BREVO_API_KEY")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp-relay.brevo.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_SECURE = os.getenv("SMTP_SECURE", "false") == "true"
SMTP_USER = os.getenv("SMTP_USER", "b0cea3001@smtp-brevo.com")

# --- Cloudinary ---
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUDNAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_APISEC")
