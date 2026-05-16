import aiosqlite

DB_PATH = "sensor.db"


async def init_db(db_path: str = DB_PATH) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT    NOT NULL,
                value     REAL    NOT NULL,
                unit      TEXT    NOT NULL
            )
        """)
        await db.commit()


async def insert_reading(
    timestamp: str,
    value: float,
    unit: str,
    db_path: str = DB_PATH,
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO readings (timestamp, value, unit) VALUES (?, ?, ?)",
            (timestamp, value, unit),
        )
        await db.commit()


async def get_history(limit: int = 100, db_path: str = DB_PATH) -> list[dict]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT timestamp, value, unit FROM readings ORDER BY id DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]
