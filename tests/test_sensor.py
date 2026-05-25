import asyncio
from datetime import datetime

import pytest

from backend.sensor import SensorReader


async def _one_reading(timeout: float = 3.0) -> dict:
    reader = SensorReader()
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(reader.start(queue))
    try:
        return await asyncio.wait_for(queue.get(), timeout=timeout)
    finally:
        task.cancel()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reading_has_required_keys():
    r = await _one_reading()
    assert {"timestamp", "accel", "gyro"} <= r.keys()


@pytest.mark.asyncio
async def test_accel_has_xyz():
    r = await _one_reading()
    assert {"x", "y", "z"} == r["accel"].keys()


@pytest.mark.asyncio
async def test_gyro_has_xyz():
    r = await _one_reading()
    assert {"x", "y", "z"} == r["gyro"].keys()


@pytest.mark.asyncio
async def test_values_are_floats():
    r = await _one_reading()
    for axis in ("x", "y", "z"):
        assert isinstance(r["accel"][axis], float)
        assert isinstance(r["gyro"][axis],  float)


@pytest.mark.asyncio
async def test_timestamp_is_iso8601():
    r = await _one_reading()
    datetime.fromisoformat(r["timestamp"])  # raises if invalid


@pytest.mark.asyncio
async def test_timestamp_is_utc():
    r = await _one_reading()
    ts = datetime.fromisoformat(r["timestamp"])
    assert ts.tzinfo is not None


# ---------------------------------------------------------------------------
# Physics plausibility
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_accel_z_near_gravity():
    r = await _one_reading()
    assert 8.0 < r["accel"]["z"] < 12.0


@pytest.mark.asyncio
async def test_accel_xy_small_at_simulated_rest():
    r = await _one_reading()
    assert abs(r["accel"]["x"]) < 2.0
    assert abs(r["accel"]["y"]) < 2.0


@pytest.mark.asyncio
async def test_gyro_values_in_reasonable_range():
    r = await _one_reading()
    for axis in ("x", "y", "z"):
        assert abs(r["gyro"][axis]) < 20.0  # degrees/s


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_simulator_rate_approx_10hz():
    reader = SensorReader()
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(reader.start(queue))
    try:
        loop = asyncio.get_running_loop()
        t0 = loop.time()
        await asyncio.wait_for(queue.get(), timeout=2.0)
        await asyncio.wait_for(queue.get(), timeout=2.0)
        elapsed = loop.time() - t0
    finally:
        task.cancel()
    assert 0.05 <= elapsed <= 0.5


# ---------------------------------------------------------------------------
# Multiple readings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_readings_all_valid():
    reader = SensorReader()
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(reader.start(queue))
    try:
        readings = [
            await asyncio.wait_for(queue.get(), timeout=2.0)
            for _ in range(3)
        ]
    finally:
        task.cancel()
    for r in readings:
        assert {"timestamp", "accel", "gyro"} <= r.keys()
        assert isinstance(r["accel"]["z"], float)


@pytest.mark.asyncio
async def test_readings_have_monotonic_timestamps():
    reader = SensorReader()
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(reader.start(queue))
    try:
        r1 = await asyncio.wait_for(queue.get(), timeout=2.0)
        r2 = await asyncio.wait_for(queue.get(), timeout=2.0)
    finally:
        task.cancel()
    assert r1["timestamp"] <= r2["timestamp"]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_mode_raises_value_error():
    reader = SensorReader()
    reader.mode = "invalid_mode"
    queue: asyncio.Queue = asyncio.Queue()
    with pytest.raises(ValueError, match="Unknown SENSOR_MODE"):
        await reader.start(queue)
