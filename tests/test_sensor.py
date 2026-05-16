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
async def test_accel_z_near_gravity():
    """Simulated Z-axis acceleration should be close to 9.81 m/s²."""
    r = await _one_reading()
    assert 8.0 < r["accel"]["z"] < 12.0


@pytest.mark.asyncio
async def test_simulator_rate_approx_10hz():
    """Two consecutive readings should arrive ~0.1 s apart."""
    reader = SensorReader()
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(reader.start(queue))
    try:
        t0 = asyncio.get_event_loop().time()
        await asyncio.wait_for(queue.get(), timeout=2.0)
        await asyncio.wait_for(queue.get(), timeout=2.0)
        elapsed = asyncio.get_event_loop().time() - t0
    finally:
        task.cancel()
    assert 0.05 <= elapsed <= 0.5
