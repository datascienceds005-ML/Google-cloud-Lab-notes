"""
routers/admin.py
STATUS: PARTIAL. Converted so far: the 4 /api/dashboard/* endpoints
(server.js lines 473-706).

STILL TO CONVERT from server.js (do not treat this router as complete):
  - line 777:  app.get('/users', ...)                    — ~900 lines, largest single handler in the file
  - line 1733: app.get('/api/interns-count', ...)
  - line 1748: app.get('/api/interns', authenticateToken, ...)
  - line 2215: app.post("/api/login", ...)
  - line 2333: app.post('/api/forgotpass', ...)
  - line 2367: app.post("/api/register", ...)
  - line 2419: app.get('/api/getintern/:id', ...)
  - line 2447: app.put('/api/interns/updateintern/:id', ...)
  - line 2515: app.put("/api/interns/updateimage/:id", ...)
  - line 1927: app.get('/api/departments/performance', ...)
  - line 3376: app.get('/api/dashboard-stats', ...)  (note: distinct from /api/dashboard/stats above)
These are the remaining Admin-domain endpoints and will be added in the
next pass.
"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from database import execute_query
from auth import authenticate_token
from utils import get_today_ist, format_time_ago, format_weekly_data

router = APIRouter(tags=["admin"])


@router.get("/api/dashboard/stats")
async def dashboard_stats(user: dict = Depends(authenticate_token)):
    """Mirrors app.get('/api/dashboard/stats', authenticateToken, ...) —
    server.js lines 473-576."""
    try:
        today = get_today_ist()

        total_interns = await execute_query(
            'SELECT COUNT(*) as count FROM Interns WHERE status = "Active"'
        )
        new_hires = await execute_query(
            "SELECT COUNT(*) as count FROM Interns WHERE start_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)"
        )
        today_attendance = await execute_query(
            "SELECT status, COUNT(*) as count FROM Attendance WHERE attendance_date = %s GROUP BY status",
            (today,),
        )
        pending_leave = await execute_query(
            'SELECT COUNT(*) as count FROM leave_requests WHERE status = "Pending"'
        )
        on_leave = await execute_query(
            'SELECT COUNT(*) as count FROM leave_requests WHERE status = "Approved" '
            "AND CURDATE() BETWEEN from_date AND to_date"
        )
        approved_leaves = await execute_query(
            'SELECT COUNT(*) as count FROM leave_requests WHERE status = "Approved"'
        )
        rejected_leaves = await execute_query(
            'SELECT COUNT(*) as count FROM leave_requests WHERE status = "Rejected"'
        )
        dept_data = await execute_query(
            """
            SELECT department, COUNT(*) as count
            FROM Interns
            WHERE department IS NOT NULL AND status = "Active"
            GROUP BY department
            """
        )
        this_week_data = await execute_query(
            """
            SELECT
                DAYNAME(attendance_date) as day_name,
                COUNT(CASE WHEN status = 'Present' THEN 1 END) * 100.0 / COUNT(*) as attendance_rate
            FROM Attendance
            WHERE attendance_date BETWEEN DATE_SUB(CURDATE(), INTERVAL 6 DAY) AND CURDATE()
            GROUP BY DAYNAME(attendance_date), attendance_date
            ORDER BY attendance_date
            """
        )
        last_week_data = await execute_query(
            """
            SELECT
                DAYNAME(attendance_date) as day_name,
                COUNT(CASE WHEN status = 'Present' THEN 1 END) * 100.0 / COUNT(*) as attendance_rate
            FROM Attendance
            WHERE attendance_date BETWEEN DATE_SUB(CURDATE(), INTERVAL 13 DAY) AND DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            GROUP BY DAYNAME(attendance_date), attendance_date
            ORDER BY attendance_date
            """
        )

        weekly_attendance = {
            "thisWeek": format_weekly_data(this_week_data),
            "lastWeek": format_weekly_data(last_week_data),
        }

        attendance_stats = {"present": 0, "absent": 0, "leave": 0, "late": 0}
        for row in today_attendance:
            attendance_stats[row["status"].lower()] = row["count"]

        departments = ["Technology", "Human Resources", "Sales", "UI/UX", "Finance"]
        department_stats = {}
        for dept in departments:
            found = next((d for d in dept_data if d["department"] == dept), None)
            department_stats[dept] = found["count"] if found else 0

        return {
            "totalInterns": total_interns[0]["count"],
            "newHires": new_hires[0]["count"],
            "attendance": attendance_stats,
            "pendingLeave": pending_leave[0]["count"],
            "ApprovedLeaves": approved_leaves[0]["count"],
            "RejectedLeaves": rejected_leaves[0]["count"],
            "onLeave": on_leave[0]["count"],
            "departments": department_stats,
            "weeklyAttendance": weekly_attendance,
        }
    except Exception as error:
        print(f"Error fetching dashboard stats: {error}")
        return JSONResponse(status_code=500, content={"error": "Failed to fetch dashboard stats"})


@router.get("/api/dashboard/attendance")
async def dashboard_attendance(limit: int = Query(default=50), user: dict = Depends(authenticate_token)):
    """Mirrors app.get('/api/dashboard/attendance', authenticateToken, ...)
    — server.js lines 579-613."""
    try:
        today = get_today_ist()
        rows = await execute_query(
            """
            SELECT
                i.name,
                i.internrole as role,
                i.department as dept,
                a.check_in as checkin,
                a.status,
                a.attendance_date
            FROM Attendance a
            JOIN Interns i ON a.intern_id = i.intern_id
            WHERE a.attendance_date = %s
            ORDER BY i.name
            LIMIT %s
            """,
            (today, int(limit)),
        )
        return [
            {
                "name": row["name"],
                "role": row["role"],
                "dept": row["dept"] or "Unassigned",
                "checkin": row["checkin"] or "—",
                "status": row["status"],
            }
            for row in rows
        ]
    except Exception as error:
        print(f"Error fetching attendance data: {error}")
        return JSONResponse(status_code=500, content={"error": "Failed to fetch attendance data"})


@router.get("/api/dashboard/leave-requests")
async def dashboard_leave_requests(user: dict = Depends(authenticate_token)):
    """Mirrors app.get('/api/dashboard/leave-requests', authenticateToken, ...)
    — server.js lines 616-659."""
    try:
        rows = await execute_query(
            """
            SELECT
                lr.id,
                lr.intern_id,
                i.department,
                lr.from_date as fromDate,
                lr.to_date as toDate,
                lr.number_of_working_days as days,
                lr.reason,
                lr.status,
                lr.leave_type,
                i.name as name,
                lr.requested_at as requestedAt
            FROM leave_requests lr
            JOIN Interns i ON lr.intern_id = i.intern_id
            ORDER BY lr.requested_at DESC
            LIMIT 20
            """
        )
        print(rows)
        leave_requests = [
            {
                "id": row["id"],
                "intern_id": row["intern_id"],
                "department": row["department"],
                "name": row["name"],
                "type": row["leave_type"],
                "startDate": row["fromDate"],
                "endDate": row["toDate"],
                "dates": row["fromDate"]
                if row["fromDate"] == row["toDate"]
                else f"{row['fromDate']}\u2013{row['toDate']}",
                "reason": row["reason"],
                "days": row["days"],
                "status": row["status"],
            }
            for row in rows
        ]
        print("leave request", leave_requests)
        return leave_requests
    except Exception as error:
        print(f"Error fetching leave requests: {error}")
        return JSONResponse(status_code=500, content={"error": "Failed to fetch leave requests"})


@router.get("/api/dashboard/pipeline")
async def dashboard_pipeline(user: dict = Depends(authenticate_token)):
    """Mirrors app.get('/api/dashboard/pipeline', authenticateToken, ...)
    — server.js lines 662-679. Original returns hardcoded mock data
    (no recruitment table exists yet) — preserved exactly, including the
    hardcoded values and colors."""
    try:
        return [
            {"stage": "Applied", "count": 40, "color": "#6366f1", "max": 40},
            {"stage": "Screening", "count": 18, "color": "#8b5cf6", "max": 30},
            {"stage": "Interview", "count": 10, "color": "#a78bfa", "max": 30},
            {"stage": "Selected", "count": 4, "color": "#16a34a", "max": 30},
        ]
    except Exception as error:
        print(f"Error fetching pipeline data: {error}")
        return JSONResponse(status_code=500, content={"error": "Failed to fetch pipeline data"})


@router.get("/api/dashboard/activities")
async def dashboard_activities(user: dict = Depends(authenticate_token)):
    """Mirrors app.get('/api/dashboard/activities', authenticateToken, ...)
    — server.js lines 682-706."""
    try:
        rows = await execute_query(
            """
            SELECT
                'New employee onboarded' as activity,
                CONCAT(i.name, ' (', i.internrole, ')') as details,
                i.created_at as timestamp
            FROM Interns i
            WHERE i.created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            ORDER BY i.created_at DESC
            LIMIT 10
            """
        )
        return [
            {"text": f"{row['activity']} \u2014 {row['details']}", "time": format_time_ago(row["timestamp"])}
            for row in rows
        ]
    except Exception as error:
        print(f"Error fetching activities: {error}")
        return JSONResponse(status_code=500, content={"error": "Failed to fetch activities"})
