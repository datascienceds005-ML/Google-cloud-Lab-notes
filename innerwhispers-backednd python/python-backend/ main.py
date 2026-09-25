"""
main.py
FastAPI app instance, middleware, and router mounting.
Equivalent to the top-level app.use(...) / app.listen(...) wiring in
server.js.

STATUS: multi-phase conversion, in progress. `finance` (Phase 1) and
`notifications` (Phase 2) are fully converted and mounted below.
`admin`, `doctor`, and `intern` (Phases 3-5) are not yet converted —
do not deploy this until those land too (see the phase plan in chat).
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

import config
from database import init_db_pool, close_db_pool
from routers import finance, notifications
# from routers import admin, doctor, intern  # Phases 3-5


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Equivalent of the async IIFE that created the MySQL pool at
    # server.js startup, including initializeDatabase().
    await init_db_pool()
    yield
    await close_db_pool()


app = FastAPI(title="InnerWhispers API", lifespan=lifespan)

# app.use(compression()) → GZipMiddleware
app.add_middleware(GZipMiddleware)

# app.use(helmet()) has no single FastAPI equivalent; the closest
# built-in is TrustedHostMiddleware plus manually setting the security
# headers helmet applies by default. Adding the headers explicitly below
# rather than silently dropping helmet's behavior.
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Strict-Transport-Security"] = "max-age=15552000; includeSubDomains"
    return response

# app.use(cors({ origin: "*", methods: "GET,POST,PUT,DELETE,OPTIONS", ... }))
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)
# NOTE: allow_origins=["*"] together with allow_credentials=True is
# rejected by browsers per the CORS spec (unlike Express's cors package,
# which lets you get away with it). The original server.js config was
# already invalid in practice for credentialed requests — flagging this
# so it isn't silently "fixed" without you knowing the original had the
# same latent bug.


@app.get("/")
async def root():
    """Mirrors app.get('/', ...) — server.js line 439."""
    return "🚀 API is running on Hostinger"


@app.get("/health")
async def health():
    """Mirrors the *second* app.get('/health', ...) at server.js line 754,
    which is the one that actually executes (Express uses the last
    matching handler when a path+method is registered twice — the first
    /health at line 441 is dead code, preserved-in-spirit by simply not
    being ported)."""
    from database import execute_query
    from fastapi import Response
    try:
        result = await execute_query("SELECT 1")
        if result and result[0].get("1") == 1:
            return Response(content="", status_code=200)
        return Response(content="", status_code=500)
    except Exception:
        return Response(content="", status_code=500)


app.include_router(finance.router)
app.include_router(notifications.router)
# app.include_router(admin.router)   # Phase 5
# app.include_router(doctor.router)  # Phase 4
# app.include_router(intern.router)  # Phase 3

# NOTE on Socket.IO: server.js wraps the Express app in a raw http.Server
# and attaches `const { Server } = require("socket.io")` for real-time
# events (attendance-update, personal-attendance, etc. — see
# processInternCheckIn). FastAPI has no built-in equivalent; the
# standard approach is python-socketio's ASGI app mounted alongside this
# one, e.g.:
#     import socketio
#     sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
#     app = socketio.ASGIApp(sio, other_asgi_app=app)
# This will be wired in once the intern/attendance router (Phase 3) that
# actually emits those events is converted, so the socket event names
# and payloads can be ported alongside their triggering endpoints.

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=config.PORT, reload=(config.NODE_ENV != "production"))
