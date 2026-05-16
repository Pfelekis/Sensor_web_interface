import asyncio
from datetime import datetime

import pytest

from backend.sensor import SensorReader


async def _get_reading(timeout: float = 3.0) -> dict:
    reader = SensorReader()
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(reader.start(queue))
    try:
        return await asyncio.wait_for(queue.get(), timeout=timeout)
    finally:
        task.cancel()


@pytest.mark.asyncio
async def test_simulator_has_required_keys():
    reading = await _get_reading()
    assert {"timestamp", "value", "unit"} <= reading.keys()


@pytest.mark.asyncio
async def test_simulator_value_is_float():
    reading = await _get_reading()
    assert isinstance(reading["value"], float)


@pytest.mark.asyncio
async def test_simulator_timestamp_is_iso8601():
    reading = await _get_reading()
    datetime.fromisoformat(reading["timestamp"])  # raises if invalid


@pytest.mark.asyncio
async def test_simulator_interval_approx_one_second():
    reader = SensorReader()
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(reader.start(queue))
    try:
        t0 = asyncio.get_event_loop().time()
        await asyncio.wait_for(queue.get(), timeout=3.0)
        await asyncio.wait_for(queue.get(), timeout=3.0)
        elapsed = asyncio.get_event_loop().time() - t0
    finally:
        task.cancel()
    # Two readings: first arrives <1s, second ~1s later; total 0.8-2.4s
    assert 0.8 <= elapsed <= 2.4
