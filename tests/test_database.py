import pytest
import aiosqlite

from backend.database import get_history, init_db, insert_reading


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
    await insert_reading("2024-01-01T00:00:00+00:00", 23.5, "°C", db_path=db)
    rows = await get_history(db_path=db)
    assert len(rows) == 1
    assert rows[0]["value"] == 23.5
    assert rows[0]["unit"] == "°C"


@pytest.mark.asyncio
async def test_get_history_respects_limit(db):
    for i in range(10):
        await insert_reading(f"2024-01-01T00:00:{i:02d}+00:00", float(i), "°C", db_path=db)
    rows = await get_history(limit=5, db_path=db)
    assert len(rows) == 5


@pytest.mark.asyncio
async def test_get_history_newest_first(db):
    await insert_reading("2024-01-01T00:00:01+00:00", 1.0, "°C", db_path=db)
    await insert_reading("2024-01-01T00:00:02+00:00", 2.0, "°C", db_path=db)
    rows = await get_history(db_path=db)
    assert rows[0]["value"] == 2.0
    assert rows[1]["value"] == 1.0
