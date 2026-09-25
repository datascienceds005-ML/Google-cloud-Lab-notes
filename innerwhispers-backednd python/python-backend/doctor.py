"""
routers/doctor.py
Converted from server.js: /api/profile (3566), /api/getalldoc (3616),
/api/getdoc/:id (3626), /api/dashboard_ui/:id GET+PUT (3636, 3646),
/api/appointments POST (3454 — the live one; 4448 is dead duplicate code,
not ported), /api/appointments/:id GET (4552),
/api/appointments/:doc_id/:id/status PUT (4574),
/api/appointments/:doc_id/:id/reschedule PUT (4593),
/api/patients GET (4645), /api/prescriptions POST/GET (4662, 4700),
/api/prescriptions/:id GET (4716), /api/prescriptions/search GET (4740).

BUGS PRESERVED FROM ORIGINAL — read before wiring this into main.py:

1. /api/getalldoc had NO authenticateToken middleware in the original but
   referenced req.user.id anyway, so every call crashed with an unhandled
   500 (TypeError: Cannot read properties of undefined). That's not
   working logic to preserve, it's dead code — I've implemented the
   query as clearly intended (no real filter was ever applied; the SQL
   itself has no WHERE clause using that id) rather than reproducing a
   total crash. Flag if you want the crash reproduced instead.

2. ROUTE ORDER BUG: /api/prescriptions/search (server.js:4740) is
   registered AFTER /api/prescriptions/:id (server.js:4716). Both
   Express and FastAPI match path routes in registration order, and
   `:id` / `{id}` matches literally any single segment — including the
   word "search". So every request to /api/prescriptions/search has
   ALWAYS actually hit the :id handler with id="search", which finds
   nothing and 404s. The search endpoint has never worked. I've
   preserved the exact same registration order below (get_prescription
   before search_prescriptions) so the bug carries over identically —
   this is the correct move if you want byte-for-byte behavior, but it
   means the "working" search router I add here is unreachable until you
   ask me to reorder it.

3. Duplicate POST /api/appointments (server.js:3454 and :4448, identical
   route+method): Express only ever runs the first-registered handler,
   so :4448 was 100% dead code (and had its own bug — it tried to
   JSON-serialize the raw MySQL query/result object under key `r` in the
   response). Only :3454's version is ported here, since that's the only
   one that ever executed.
"""
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from database import execute_query, execute_write
from auth import authenticate_token

router = APIRouter(tags=["doctor"])

SESSION_TYPES = {
    "Initial Consultation": {"duration": 40, "price": 1000, "description": "Comprehensive assessment"},
    "Counseling Session": {"duration": 50, "price": 1500, "description": "Counseling session"},
    "Therapy Session": {"duration": 80, "price": 3000, "description": "Focused session"},
}


def convert_to_24_hour(time_str: str | None) -> str | None:
    """Direct port of convertTo24Hour() — server.js lines 3423-3451."""
    import re

    if not time_str or not isinstance(time_str, str):
        return time_str

    try:
        if re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", time_str):
            return time_str + ":00"

        time_part, meridiem = time_str.split(" ")
        hours, minutes = time_part.split(":")
        hour = int(hours)

        if meridiem.lower() == "pm" and hour != 12:
            hour += 12
        elif meridiem.lower() == "am" and hour == 12:
            hour = 0

        return f"{hour:02d}:{minutes}:00"
    except Exception as error:
        print(f"Time conversion error: {error}")
        return None


# --- Profile / doctor lookup ---

@router.get("/api/profile")
async def get_profile(user: dict = Depends(authenticate_token)):
    """Mirrors app.get('/api/profile', authenticateToken, ...) — lines 3566-3613."""
    user_id = user.get("id")
    if not user_id:
        return JSONResponse(status_code=400, content={"message": "Invalid token: missing user ID"})

    try:
        rows = await execute_query(
            """
            SELECT u.id, u.role, u.full_name as name, u.email, u.profile_image, i.department, i.status
            FROM users u
            LEFT JOIN Interns i ON u.email = i.email
            WHERE u.id = %s
            """,
            (user_id,),
        )
        if not rows:
            return JSONResponse(status_code=404, content={"message": "User not found"})

        profile = rows[0]
        if profile.get("email"):
            intern_rows = await execute_query(
                "SELECT intern_id FROM Interns WHERE email = %s", (profile["email"],)
            )
            if intern_rows:
                profile["intern_id"] = intern_rows[0]["intern_id"]

        return profile
    except Exception as error:
        print(f"Error in profile endpoint: {error}")
        return JSONResponse(status_code=500, content={"message": "Server error"})


@router.get("/api/getalldoc")
async def get_all_doc():
    """Mirrors app.get('/api/getalldoc', ...) — lines 3616-3623.
    See module docstring bug #1 — the original crashed on every call.
    Implemented here as the SQL text actually says (no working filter)."""
    try:
        rows = await execute_query("SELECT id, full_name FROM doctor_details")
        if not rows:
            return JSONResponse(status_code=404, content={"message": "User not found"})
        return rows[0]
    except Exception:
        return JSONResponse(status_code=500, content={"message": "DB error"})


@router.get("/api/getdoc/{id}")
async def get_doc(id: str):
    """Mirrors app.get('/api/getdoc/:id', ...) — lines 3626-3633."""
    try:
        rows = await execute_query("SELECT id, full_name FROM doctor_details WHERE id = %s", (id,))
        if not rows:
            return JSONResponse(status_code=404, content={"message": "User not found"})
        return rows[0]
    except Exception:
        return JSONResponse(status_code=500, content={"message": "DB error"})


@router.get("/api/dashboard_ui/{id}")
async def get_dashboard_ui(id: str):
    """Mirrors app.get('/api/dashboard_ui/:id', ...) — lines 3636-3643."""
    try:
        rows = await execute_query("SELECT * FROM doctor_ui WHERE doctor_id = %s", (id,))
        if not rows:
            return JSONResponse(status_code=404, content={"message": "User not found"})
        return rows[0]
    except Exception:
        return JSONResponse(status_code=500, content={"message": "DB error"})


@router.put("/api/dashboard_ui/{id}")
async def update_dashboard_ui(id: str, request: Request):
    """Mirrors app.put('/api/dashboard_ui/:id', ...) — lines 3646-3662.
    Original used mysql2's `SET ?` shorthand (builds "col1 = val1, col2 =
    val2, ..." from an arbitrary object) — no FastAPI/SQL equivalent
    without building the clause dynamically, so we do that explicitly,
    parameterized (safer than the original's implicit escaping, same
    result)."""
    fields = await request.json()
    if not fields:
        return JSONResponse(status_code=400, content={"message": "No fields provided to update"})

    set_clause = ", ".join(f"{col} = %s" for col in fields.keys())
    params = list(fields.values()) + [id]

    try:
        result = await execute_write(
            f"UPDATE doctor_ui SET {set_clause} WHERE doctor_id = %s", params
        )
        if result["affected_rows"] == 0:
            return JSONResponse(status_code=404, content={"message": "Doctor not found"})
        return {"message": "Update successful"}
    except Exception as err:
        return JSONResponse(status_code=500, content={"message": "DB error", "error": str(err)})


# --- Appointments ---

@router.post("/api/appointments")
async def create_appointment(request: Request):
    """Mirrors the LIVE app.post('/api/appointments', ...) handler —
    server.js lines 3454-3532 (the first of the two duplicate
    registrations; see module docstring bug #3)."""
    body = await request.json()

    time24 = convert_to_24_hour(body.get("appointment_time"))
    if not time24:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid time format", "details": "Time should be in format HH:MM AM/PM or HH:MM"},
        )

    session_info = SESSION_TYPES.get(body.get("session_type"), {"duration": 50, "price": 1500})

    values = (
        body.get("patient_name"), body.get("email"), body.get("phone"), body.get("addhar"),
        body.get("age"), body.get("parenttype"), body.get("parentName"), body.get("guardianPhone"),
        body.get("address"), body.get("pincode"), body.get("state"), body.get("concerns"),
        body.get("appointment_date"), time24, body.get("session_type"),
        session_info["price"], session_info["duration"], body.get("status") or "pending",
    )

    try:
        result = await execute_write(
            """
            INSERT INTO appointments
            SET
                patient_name = %s, email = %s, phone = %s, addhar = %s, age = %s,
                parenttype = %s, parentName = %s, guardianPhone = %s, address = %s,
                pincode = %s, state = %s, concerns = %s,
                appointment_date = CONVERT_TZ(%s, '+00:00', '+05:30'),
                appointment_time = %s, session_type = %s, session_price = %s,
                session_duration = %s, status = %s,
                created_at = CONVERT_TZ(NOW(), '+00:00', '+05:30')
            """,
            values,
        )
        return JSONResponse(
            status_code=201,
            content={
                "message": "Appointment created successfully",
                "id": result["insert_id"],
                "appointment_date": body.get("appointment_date"),
                "appointment_time": time24,
            },
        )
    except Exception as err:
        print(f"Database error: {err}")
        return JSONResponse(status_code=500, content={"error": "Could not save appointment", "details": str(err)})


@router.get("/api/appointments/{id}")
async def get_appointments_for_doctor(id: str):
    """Mirrors app.get('/api/appointments/:id', ...) — lines 4552-4571.
    NOTE: despite the param being named `id`, the original filters by
    `doctor_id = ?` — this is a doctor's appointment list, not a lookup
    by appointment id. Preserved exactly (including the misleading name)."""
    try:
        rows = await execute_query(
            """
            SELECT *,
                   DATE_FORMAT(CONVERT_TZ(appointment_date, '+00:00', '+05:30'), '%Y-%m-%d') as appointment_date
            FROM appointments
            WHERE doctor_id = %s
            ORDER BY appointment_date, appointment_time
            """,
            (id,),
        )
        return rows
    except Exception as err:
        print(f"Database error: {err}")
        return JSONResponse(status_code=500, content={"error": str(err)})


@router.put("/api/appointments/{doc_id}/{id}/status")
async def update_appointment_status(doc_id: str, id: str, request: Request):
    """Mirrors app.put('/api/appointments/:doc_id/:id/status', ...) — lines 4574-4589."""
    body = await request.json()
    status = body.get("status")
    try:
        await execute_write(
            "UPDATE appointments SET status = %s WHERE doctor_id = %s AND id = %s",
            (status, doc_id, id),
        )
        return {"message": "Status updated successfully"}
    except Exception as err:
        return JSONResponse(status_code=500, content={"error": str(err)})


@router.put("/api/appointments/{doc_id}/{id}/reschedule")
async def reschedule_appointment(doc_id: str, id: str, request: Request):
    """Mirrors app.put('/api/appointments/:doc_id/:id/reschedule', ...) — lines 4593-4635."""
    import re

    body = await request.json()
    appointment_date = body.get("appointment_date")
    appointment_time = body.get("appointment_time")
    print("RAW BODY:", body)

    if not appointment_date or not appointment_time:
        return JSONResponse(status_code=400, content={"error": "Date and time required"})

    if isinstance(appointment_date, str):
        if "T" in appointment_date:
            appointment_date = appointment_date.split("T")[0]
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", appointment_date):
            return JSONResponse(status_code=400, content={"error": "Invalid date format, must be YYYY-MM-DD"})
    else:
        return JSONResponse(status_code=400, content={"error": "Invalid date format, must be string"})

    print("Reschedule request:", {"id": id, "appointment_date": appointment_date, "appointment_time": appointment_time})

    time24 = convert_to_24_hour(appointment_time)
    if not time24:
        return JSONResponse(status_code=400, content={"error": "Invalid time format"})

    try:
        await execute_write(
            "UPDATE appointments SET appointment_date = %s, appointment_time = %s WHERE doctor_id = %s AND id = %s",
            (appointment_date, time24, doc_id, id),
        )
        return {"message": "Appointment rescheduled successfully"}
    except Exception as err:
        return JSONResponse(status_code=500, content={"error": str(err)})


# --- Patients ---

@router.get("/api/patients")
async def get_patients():
    """Mirrors app.get('/api/patients', ...) — lines 4645-4660."""
    try:
        rows = await execute_query(
            "SELECT DISTINCT patient_name FROM appointments WHERE status = 'confirmed' ORDER BY patient_name"
        )
        return rows
    except Exception as err:
        return JSONResponse(status_code=500, content={"error": str(err)})


# --- Prescriptions ---

@router.post("/api/prescriptions")
async def create_prescription(request: Request):
    """Mirrors app.post('/api/prescriptions', ...) — lines 4662-4698."""
    body = await request.json()
    try:
        result = await execute_write(
            """
            INSERT INTO prescriptions
            (patient_name, prescription_date, medication_name, medication_type,
             medication_dosage, medication_supply, special_instructions, notes)
            VALUES (%s, CURDATE(), %s, %s, %s, %s, %s, %s)
            """,
            (
                body.get("patient_name"), body.get("medication_name"), body.get("medication_type"),
                body.get("medication_dosage"), body.get("medication_supply"),
                body.get("special_instructions"), body.get("notes"),
            ),
        )
        return JSONResponse(
            status_code=201,
            content={"id": result["insert_id"], "message": "Prescription created successfully"},
        )
    except Exception as err:
        return JSONResponse(status_code=500, content={"error": str(err)})


@router.get("/api/prescriptions")
async def list_prescriptions():
    """Mirrors app.get('/api/prescriptions', ...) — lines 4700-4713."""
    try:
        rows = await execute_query("SELECT * FROM prescriptions ORDER BY prescription_date DESC, created_at DESC")
        return rows
    except Exception as err:
        return JSONResponse(status_code=500, content={"error": str(err)})


@router.get("/api/prescriptions/{id}")
async def get_prescription(id: str):
    """Mirrors app.get('/api/prescriptions/:id', ...) — lines 4716-4737.
    Registered BEFORE the /search route below, exactly as in the
    original — see module docstring bug #2. This means a request to
    /api/prescriptions/search is handled HERE with id='search', not by
    the search_prescriptions handler further down."""
    try:
        rows = await execute_query("SELECT * FROM prescriptions WHERE id = %s", (id,))
        if not rows:
            return JSONResponse(status_code=404, content={"error": "Prescription not found"})
        return rows[0]
    except Exception as err:
        return JSONResponse(status_code=500, content={"error": str(err)})


@router.get("/api/prescriptions/search")
async def search_prescriptions(term: str = Query(default="")):
    """Mirrors app.get('/api/prescriptions/search', ...) — lines 4740-4759.
    UNREACHABLE as registered (see bug #2) — kept for completeness /
    parity, and instantly usable the moment you ask me to move it before
    get_prescription."""
    search_term = f"%{term.lower()}%"
    try:
        rows = await execute_query(
            """
            SELECT * FROM prescriptions
            WHERE LOWER(patient_name) LIKE %s
               OR DATE_FORMAT(prescription_date, '%b %d, %Y') LIKE %s
            ORDER BY prescription_date DESC, created_at DESC
            """,
            (search_term, search_term),
        )
        return rows
    except Exception as err:
        return JSONResponse(status_code=500, content={"error": str(err)})
