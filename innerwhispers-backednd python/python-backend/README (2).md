# InnerWhispers — Python/FastAPI Backend

Conversion of `server.js` to FastAPI. **Status: 35 of 94 endpoints converted**
(Finance ✅, Notifications ✅, Doctor/Clinical ✅, Admin dashboard-stats ✅).
Not yet converted: the `/users` admin block, intern login/register/CRUD,
and the whole Intern domain (attendance, tasks, leave, reports, documents).
See each router file's module docstring for exact server.js line-number
mappings and any preserved bugs from the original.

## Setup (GitHub Codespaces / any bash terminal)

```bash
# 1. Navigate into the Python backend directory
cd python-backend

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Codespaces is Linux, so this is the right activation line
# (venv) should now prefix your terminal prompt

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your local env file and fill in real values
cp .env.example .env
nano .env        # or use the Codespaces file explorer — fill in DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, SECRET_KEY at minimum

# 5. Run the server
uvicorn main:app --host 0.0.0.0 --port 3006 --reload
```

You should see:
```
✅ Connected to MySQL (pool)
✅ Database initialized
INFO:     Uvicorn running on http://0.0.0.0:3006
```

### Avoiding port conflicts
If `server.js` (Node) might already be running on the same port, either stop it first (`Ctrl+C` in its terminal) or run Python on a different port:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
Both can run simultaneously as long as they're on different ports — useful for comparing responses side-by-side while you migrate route by route.

### Accessing Swagger UI in Codespaces
Codespaces auto-forwards the port. When `uvicorn` starts:
1. A popup/notification appears bottom-right — click **"Open in Browser"**.
2. Or go to the **Ports** tab (next to Terminal) → find port `3006` → click the 🌐 globe icon.
3. Append `/docs` to the forwarded URL, e.g. `https://your-codespace-name-3006.app.github.dev/docs`.

If the port shows as **Private**, right-click it in the Ports tab → **Port Visibility** → **Public** (or stay Private and just open it yourself while logged in — Private still works for you, just not for sharing the link).

You can also test with Postman by pointing it at that same forwarded URL instead of `localhost`.

### Quick health check
```bash
curl http://localhost:3006/health
curl http://localhost:3006/api/summary   # a finance endpoint that needs no auth token
```

## Re-activating the venv later
Every new terminal session, you only need:
```bash
cd python-backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 3006 --reload
```
(Skip `pip install` unless `requirements.txt` changed.)
