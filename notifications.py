"""
routers/notifications.py
Converted 1:1 from server.js lines 2092-2214.

Auth note: 3 of these 5 endpoints require authenticateToken in the
original (GET /api/notifications, PUT /api/notifications/read-all,
GET /api/notifications/unread-count) — preserved below. The other two
(POST /api/notifications, PUT /api/notifications/:id/read) had no auth
in the original; also preserved as-is. Worth confirming that's
intentional (anyone can currently create a notification or mark any
single notification as read without a token).
"""
from fastapi import APIRouter, Depends, Query, Path
from fastapi.responses import JSONResponse

from database import execute_query, execute_write
from auth import authenticate_token
from services.notifications import create_notification

router = APIRouter(tags=["notifications"])


@router.get("/api/notifications")
async def get_notifications(
    limit: int = Query(default=20),
    unread_only: str = Query(default="false"),
    user: dict = Depends(authenticate_token),
):
    """Mirrors app.get('/api/notifications', authenticateToken, ...) —
    lines 2092-2128."""
    try:
        user_id = user.get("id")
        user_role = user.get("role")

        where_clause = "WHERE 1=1"
        params: list = []

        # Filter by user or role — same if/elif as the original (id takes
        # priority; role-only filtering only applies when id is absent).
        if user_id:
            where_clause += ' AND (target_user_id = %s OR target_role = "all" OR target_role = %s)'
            params.extend([user_id, user_role])
        elif user_role:
            where_clause += ' AND (target_role = %s OR target_role = "all")'
            params.append(user_role)

        if unread_only == "true":
            where_clause += " AND is_read = false"

        sql = f"""
            SELECT id, notify as title, description, type, target_user_id, target_role, is_read as isRead,
                   created_at as createdAt
            FROM Notifications
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %s
        """
        rows = await execute_query(sql, [*params, int(limit)])
        return rows
    except Exception as error:
        print(f"Error fetching notifications: {error}")
        return JSONResponse(status_code=500, content={"message": "Server error"})


@router.post("/api/notifications")
async def post_notification(payload: dict):
    """Mirrors app.post('/api/notifications', ...) — lines 2130-2149.
    No auth on this one in the original — preserved as-is (see module
    docstring)."""
    notify = payload.get("notify")
    description = payload.get("description")
    type_ = payload.get("type")
    target_user_id = payload.get("targetUserId")
    target_role = payload.get("targetRole", "all")

    if not notify or not description:
        return JSONResponse(status_code=400, content={"error": "notify and description are required"})

    try:
        notification_id = await create_notification(
            notify, description, type_ or "info", target_user_id, target_role
        )
        return {
            "success": True,
            "message": "Notification created successfully",
            "id": notification_id,
        }
    except Exception as error:
        print(f"Error creating notification: {error}")
        return JSONResponse(status_code=500, content={"error": "Failed to create notification"})


@router.put("/api/notifications/{id}/read")
async def mark_notification_read(id: str = Path(...)):
    """Mirrors app.put('/api/notifications/:id/read', ...) — lines
    2151-2162. No auth in the original — preserved as-is. Also note: no
    ownership check either, so (as in the original) any caller can mark
    any notification id as read."""
    try:
        await execute_write("UPDATE Notifications SET is_read = TRUE WHERE id = %s", (id,))
        return {"success": True, "message": "Notification marked as read"}
    except Exception as error:
        print(f"Error marking notification as read: {error}")
        return JSONResponse(status_code=500, content={"error": "Failed to update notification"})


@router.put("/api/notifications/read-all")
async def mark_all_notifications_read(user: dict = Depends(authenticate_token)):
    """Mirrors app.put('/api/notifications/read-all', authenticateToken, ...)
    — lines 2164-2187.

    BUG PRESERVED FROM ORIGINAL: in the `elif userRole` branch, the source
    does `params.push(userRole, userRole)` — two values — against a WHERE
    clause with only one `?` placeholder:
        whereClause += ' AND (target_role = ? OR target_role = "all")'
    This param/placeholder mismatch only fires when a valid JWT has a
    role but no id (uncommon, but possible depending on what your token
    payloads look like). In Node/mysql2 this either silently drops the
    extra value or errors depending on driver version; in Python,
    aiomysql/PyMySQL will raise on the mismatched param count. I've kept
    the double-push to match the source exactly rather than silently
    fixing it — flag if you'd rather I correct it to a single push here.
    """
    try:
        user_id = user.get("id")
        user_role = user.get("role")

        where_clause = "WHERE 1=1"
        params: list = []

        if user_id:
            where_clause += ' AND (target_user_id = %s OR target_role = "all" OR target_role = %s)'
            params.extend([user_id, user_role])
        elif user_role:
            where_clause += ' AND (target_role = %s OR target_role = "all")'
            params.extend([user_role, user_role])  # preserved mismatch — see docstring

        await execute_write(f"UPDATE Notifications SET is_read = TRUE {where_clause}", params)
        return {"success": True, "message": "All notifications marked as read"}
    except Exception as error:
        print(f"Error marking all notifications as read: {error}")
        return JSONResponse(status_code=500, content={"error": "Failed to update notifications"})


@router.get("/api/notifications/unread-count")
async def get_unread_count(user: dict = Depends(authenticate_token)):
    """Mirrors app.get('/api/notifications/unread-count', authenticateToken, ...)
    — lines 2189-2213."""
    try:
        user_id = user.get("id")
        user_role = user.get("role")

        where_clause = "WHERE is_read = FALSE"
        params: list = []

        if user_id:
            where_clause += ' AND (target_user_id = %s OR target_role = "all" OR target_role = %s)'
            params.extend([user_id, user_role])
        elif user_role:
            where_clause += ' AND (target_role = %s OR target_role = "all")'
            params.append(user_role)

        rows = await execute_query(f"SELECT COUNT(*) as count FROM Notifications {where_clause}", params)
        unread_count = rows[0]["count"] if rows and rows[0].get("count") is not None else 0
        return {"unreadCount": unread_count}
    except Exception as error:
        print(f"FULL ERROR: {error}")
        return JSONResponse(status_code=500, content={"error": "Failed to fetch unread count"})
