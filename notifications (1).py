"""
services/notifications.py
Equivalent of the createNotification() helper defined inside the DB-init
IIFE in server.js (lines 1554-1593). Pulled out into a standalone service
module since Python has no natural place for "a closure defined inside
another async function" the way the original nested it inside the table-
creation block — this is functionally identical, just given a proper home.

Also carries the Notifications table DDL as a docstring reference (see
schema below) since server.js created it lazily on startup
(CREATE TABLE IF NOT EXISTS) rather than via a migration tool. If this
project doesn't already have a migrations setup, that table needs to
exist before this module's queries will work:

    CREATE TABLE IF NOT EXISTS Notifications (
        id INT AUTO_INCREMENT PRIMARY KEY,
        notify VARCHAR(255) NOT NULL,
        description TEXT NOT NULL,
        type ENUM('info', 'success', 'warning', 'error') DEFAULT 'info',
        target_user_id VARCHAR(50) NULL,
        target_role ENUM('hr', 'intern', 'all') DEFAULT 'all',
        is_read BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""
from datetime import datetime, timezone

from database import execute_write
import sockets


async def create_notification(
    notify: str,
    description: str,
    type: str = "info",
    target_user_id: str | None = None,
    target_role: str = "all",
) -> int:
    """Direct port of createNotification(). Inserts the row, then emits
    the same three conditional real-time events the original did:
      1. to `intern-{targetUserId}` room, if targetUserId is set
      2. to `hr-dashboard` room, if targetRole is 'hr' or 'all'
      3. broadcast to every connected client, if targetRole is 'intern' or 'all'

    Note the original's conditions 2 and 3 aren't mutually exclusive —
    when target_role == 'all', BOTH the hr-dashboard emit AND the global
    broadcast fire (the global broadcast reaches hr-dashboard clients
    too, so 'all' notifications go out twice to HR sockets). Preserved
    exactly as-is; flag if you want that de-duplicated.
    """
    try:
        result = await execute_write(
            "INSERT INTO Notifications (notify, description, type, target_user_id, target_role) "
            "VALUES (%s, %s, %s, %s, %s)",
            (notify, description, type, target_user_id, target_role),
        )
        notification_id = result["insert_id"]

        notification_data = {
            "id": notification_id,
            "notify": notify,
            "description": description,
            "type": type,
            "target_user_id": target_user_id,
            "target_role": target_role,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if target_user_id:
            await sockets.emit("new-notification", notification_data, room=f"intern-{target_user_id}")

        if target_role in ("hr", "all"):
            await sockets.emit("new-notification", notification_data, room="hr-dashboard")

        if target_role in ("intern", "all"):
            await sockets.emit("new-notification", notification_data)  # global broadcast

        print(f"📢 Notification created and sent: {notification_data}")
        return notification_id

    except Exception as error:
        print(f"Error creating notification: {error}")
        raise
