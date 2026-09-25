"""
database.py
Async MySQL connection pool and a raw-query execution helper that mirrors
the `executeQuery(sql, params)` function from server.js (lines 745-752):

    function executeQuery(sql, params = []) {
      return new Promise((resolve, reject) => {
        db.query(sql, params, (err, results) => {
          if (err) return reject(err);
          resolve([results]);
        });
      });
    }

Node's mysql2 returns rows as an array of plain objects (dict-like), and
`[results]` is destructured elsewhere in server.js as `const [rows] = await
executeQuery(...)`. aiomysql's DictCursor gives us the same row shape
(list[dict]), so we keep execute_query's return signature as a plain
list[dict] and drop the extra tuple wrapper (Python call sites just do
`rows = await execute_query(...)` instead of unpacking).
"""
import aiomysql
from typing import Any, Optional

import config

_pool: Optional[aiomysql.Pool] = None


async def init_db_pool() -> None:
    """Create the pool. Equivalent to the `db = await mysql.createPool(dbConfig)`
    IIFE at the top of server.js, including the timezone pin."""
    global _pool
    _pool = await aiomysql.create_pool(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        db=config.DB_NAME,
        port=config.DB_PORT,
        minsize=config.DB_POOL_MIN_SIZE,
        maxsize=config.DB_POOL_MAX_SIZE,
        autocommit=True,
        cursorclass=aiomysql.cursors.DictCursor,
    )
    # mysql2's `timezone: '+05:30'` option offsets DATETIME/TIMESTAMP I/O.
    # aiomysql has no equivalent pool option, so we set the session
    # timezone on every new connection instead (functionally identical).
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SET time_zone = %s", (config.DB_TIMEZONE,))
    print("✅ Connected to MySQL (pool)")
    await initialize_database()


async def close_db_pool() -> None:
    if _pool is not None:
        _pool.close()
        await _pool.wait_closed()


def get_pool() -> aiomysql.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized — call init_db_pool() on startup")
    return _pool


async def execute_query(sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
    """Direct equivalent of executeQuery() in server.js.
    Returns a list of dict rows for SELECTs, or an empty list for
    INSERT/UPDATE/DELETE (use execute_write() below when you need
    lastrowid / rowcount, matching Node's `result.insertId`)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            if cur.description is None:
                return []
            return await cur.fetchall()


async def execute_write(sql: str, params: tuple | list = ()) -> dict[str, Any]:
    """For INSERT/UPDATE/DELETE where the caller needs result.insertId or
    result.affectedRows (e.g. `const budgetId = result.insertId;` in the
    original /api/budgets POST handler)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            return {"insert_id": cur.lastrowid, "affected_rows": cur.rowcount}


async def execute_many(sql: str, seq_of_params: list[tuple]) -> dict[str, Any]:
    """Equivalent of mysql2's bulk `INSERT ... VALUES ?` with an array of
    row-arrays, used by the /api/budgets budget_categories bulk insert."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.executemany(sql, seq_of_params)
            return {"affected_rows": cur.rowcount}


async def initialize_database() -> None:
    """Equivalent of initializeDatabase() in server.js — creates the
    `users` table if it doesn't exist. Every other table referenced
    elsewhere in server.js (Attendance, Interns, transactions, budgets,
    budget_categories, payments, invoices, receipts, settings, etc.) is
    assumed pre-existing, exactly as in the original, which never
    CREATE TABLE IF NOT EXISTS'd them either."""
    try:
        await execute_query(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                phone VARCHAR(20),
                role VARCHAR(15) NOT NULL DEFAULT 'patient',
                profile_image VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
                last_login TIMESTAMP NULL,
                status ENUM('active', 'inactive', 'suspended') DEFAULT 'active'
            )
            """
        )
        print("✅ Database initialized")
    except Exception as err:  # noqa: BLE001 — match server.js's catch-and-log
        print(f"❌ DB Init Error: {err}")
