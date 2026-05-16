import pytest
import aiosqlite

from backend.database import get_history, init_db, insert_reading

ACCEL = {"x": 0.12, "y": -0.05, "z": 9.79}
GYRO  = {"x": 0.30, "y": -0.10, "z": 0.05}
TS    = "2024-01-01T00:00:00+00:00"


@pytest.fixture
async def db(tmp_path):
    path = str(tmp_path / "test.db")
    await init_db(path)
    return path


@pytest.mark.asyncio
async def test_init_creates_table(tmp_path):
    path = str(tmp_path / "init.db")
    await init_db(path)
    async with aiosqlite.connect(path) as conn:
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='readings'"
        ) as cur:
            row = await cur.fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_insert_and_retrieve(db):
    await insert_reading(TS, ACCEL, GYRO, db_path=db)
    rows = await get_history(db_path=db)
    assert len(rows) == 1
    assert rows[0]["accel"] == ACCEL
    assert rows[0]["gyro"]  == GYRO
    assert rows[0]["timestamp"] == TS


@pytest.mark.asyncio
async def test_get_history_respects_limit(db):
    for i in range(10):
        await insert_reading(f"2024-01-01T00:00:{i:02d}+00:00", ACCEL, GYRO, db_path=db)
    rows = await get_history(limit=5, db_path=db)
    assert len(rows) == 5


@pytest.mark.asyncio
async def test_get_history_newest_first(db):
    await insert_reading("2024-01-01T00:00:01+00:00", {"x": 1.0, "y": 1.0, "z": 1.0}, GYRO, db_path=db)
    await insert_reading("2024-01-01T00:00:02+00:00", {"x": 2.0, "y": 2.0, "z": 2.0}, GYRO, db_path=db)
    rows = await get_history(db_path=db)
    assert rows[0]["accel"]["x"] == 2.0
    assert rows[1]["accel"]["x"] == 1.0
