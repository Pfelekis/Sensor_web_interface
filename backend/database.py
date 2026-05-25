import aiosqlite

DB_PATH = "sensor.db"


async def init_db(db_path: str = DB_PATH) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT    NOT NULL,
                accel_x   REAL    NOT NULL,
                accel_y   REAL    NOT NULL,
                accel_z   REAL    NOT NULL,
                gyro_x    REAL    NOT NULL,
                gyro_y    REAL    NOT NULL,
                gyro_z    REAL    NOT NULL
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON readings(timestamp)"
        )
        await db.commit()


async def insert_reading(
    timestamp: str,
    accel: dict,
    gyro: dict,
    db_path: str = DB_PATH,
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO readings
                (timestamp, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (timestamp, accel["x"], accel["y"], accel["z"],
             gyro["x"],  gyro["y"],  gyro["z"]),
        )
        await db.commit()


async def get_history(limit: int = 100, db_path: str = DB_PATH) -> list[dict]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT timestamp, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z
            FROM readings ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        {
            "timestamp": r["timestamp"],
            "accel": {"x": r["accel_x"], "y": r["accel_y"], "z": r["accel_z"]},
            "gyro":  {"x": r["gyro_x"],  "y": r["gyro_y"],  "z": r["gyro_z"]},
        }
        for r in rows
    ]


async def get_reading_count(db_path: str = DB_PATH) -> int:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT COUNT(*) FROM readings") as cursor:
            row = await cursor.fetchone()
    return row[0] if row else 0
