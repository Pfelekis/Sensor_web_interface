import pytest
import aiosqlite

from backend.database import get_history, get_reading_count, init_db, insert_reading

ACCEL = {"x": 0.12, "y": -0.05, "z": 9.79}
GYRO  = {"x": 0.30, "y": -0.10, "z": 0.05}
TS    = "2024-01-01T00:00:00+00:00"


@pytest.fixture
async def db(tmp_path):
    path = str(tmp_path / "test.db")
    await init_db(path)
    return path


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_init_creates_readings_table(tmp_path):
    path = str(tmp_path / "init.db")
    await init_db(path)
    async with aiosqlite.connect(path) as conn:
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='readings'"
        ) as cur:
            assert await cur.fetchone() is not None


@pytest.mark.asyncio
async def test_init_creates_timestamp_index(tmp_path):
    path = str(tmp_path / "idx.db")
    await init_db(path)
    async with aiosqlite.connect(path) as conn:
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_readings_timestamp'"
        ) as cur:
            assert await cur.fetchone() is not None


@pytest.mark.asyncio
async def test_init_db_is_idempotent(tmp_path):
    path = str(tmp_path / "idem.db")
    await init_db(path)
    await init_db(path)  # must not raise


# ---------------------------------------------------------------------------
# Insert & retrieve
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insert_and_retrieve(db):
    await insert_reading(TS, ACCEL, GYRO, db_path=db)
    rows = await get_history(db_path=db)
    assert len(rows) == 1
    assert rows[0]["accel"] == ACCEL
    assert rows[0]["gyro"]  == GYRO
    assert rows[0]["timestamp"] == TS


@pytest.mark.asyncio
async def test_empty_db_returns_empty_list(db):
    rows = await get_history(db_path=db)
    assert rows == []


@pytest.mark.asyncio
async def test_float_precision_preserved(db):
    precise = {"x": 1.2345, "y": -2.3456, "z": 9.8765}
    await insert_reading(TS, precise, GYRO, db_path=db)
    rows = await get_history(db_path=db)
    for axis in ("x", "y", "z"):
        assert rows[0]["accel"][axis] == pytest.approx(precise[axis])


@pytest.mark.asyncio
async def test_negative_values_preserved(db):
    neg_accel = {"x": -1.5, "y": -2.5, "z": -9.81}
    await insert_reading(TS, neg_accel, GYRO, db_path=db)
    rows = await get_history(db_path=db)
    assert rows[0]["accel"]["z"] == pytest.approx(-9.81)


# ---------------------------------------------------------------------------
# Count helper
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_reading_count_empty(db):
    assert await get_reading_count(db_path=db) == 0


@pytest.mark.asyncio
async def test_get_reading_count_after_inserts(db):
    for i in range(5):
        await insert_reading(f"2024-01-01T00:00:0{i}+00:00", ACCEL, GYRO, db_path=db)
    assert await get_reading_count(db_path=db) == 5


# ---------------------------------------------------------------------------
# History ordering & limits
# ---------------------------------------------------------------------------

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


@pytest.mark.asyncio
async def test_get_history_default_limit_is_100(db):
    for i in range(120):
        await insert_reading(f"2024-01-01T{i // 3600:02d}:{(i % 3600) // 60:02d}:{i % 60:02d}+00:00",
                             ACCEL, GYRO, db_path=db)
    rows = await get_history(db_path=db)  # default limit=100
    assert len(rows) == 100
