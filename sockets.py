"""
sockets.py
PLACEHOLDER — real-time layer.

server.js attaches Socket.IO directly to the http.Server wrapping Express
(`const { Server } = require("socket.io")`) and emits events like
'new-notification', 'attendance-update', and 'personal-attendance' from
several handlers (createNotification, processInternCheckIn, etc.).

This module exists so those call sites can import a stable `emit()`
function now, instead of each router inventing its own no-op. It will be
replaced in Phase 3 (the intern/attendance router, which is where
Socket.IO actually gets initialized against a python-socketio
AsyncServer mounted alongside the FastAPI ASGI app) with a real
implementation that has the same signature.

Until Phase 3 lands, this logs instead of emitting, so nothing silently
disappears — you'll see in your logs exactly which events would have
gone out over the socket.
"""


async def emit(event: str, data: dict, room: str | None = None) -> None:
    """Stand-in for io.to(room).emit(event, data) / io.emit(event, data).
    room=None mirrors a global io.emit() (broadcast to all connected
    clients)."""
    if room:
        print(f"🔌 [socket stub] would emit '{event}' to room '{room}': {data}")
    else:
        print(f"🔌 [socket stub] would broadcast '{event}' to all clients: {data}")
